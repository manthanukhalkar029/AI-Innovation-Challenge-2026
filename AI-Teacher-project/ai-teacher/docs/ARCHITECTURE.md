# Architecture

## Request flow

```
                         ┌─────────────────────────┐
  Upload material  ───►  │ ingestion/extract.py     │
  (PDF/DOCX/PPTX/TXT)    │  + chunker.py            │──► TF-IDF DocumentIndex
                         │  + retriever.py          │    (retriever.py), persisted
                         └─────────────────────────┘    per session (pickle)
                                                              │
                                                              ▼
  Topic + learner profile ───────────────────────► teaching/lesson_planner.py
  (level, minutes, language, style)                          │
                                                              ▼
                                                  Structured lesson JSON
                                        (objectives, sections: explanation,
                                         example, visual_type, checkpoint_q)
                                                              │
                        ┌─────────────────────────────────────┼───────────────────────┐
                        ▼                                     ▼                       ▼
              media/video_builder.py              teaching/adaptive_engine.py   teaching/assessment.py
        (per section: slides.py diagram +                (per checkpoint            (end-of-lesson
         avatar.py talking avatar +                        answer: evaluate,         quiz generate
         tts.py narration) → ffmpeg concat                 detect misconception,     + score + report)
                        │                                   reexplain if needed)             │
                        ▼                                                                    ▼
                 lesson_<id>.mp4                                                  teaching/profile_store.py
                                                                                    (SQLite: persists per
                                                                                     student across sessions)
```

Every arrow that involves "understanding, generating, or judging text" goes
through `llm/base.py::get_provider()` — this is the single seam that
determines whether the system is running on Claude, GPT, a local Ollama
model, or the offline mock. No other module ever imports a vendor SDK
directly.

## TF-IDF by default, real vector database (FAISS) as a switch

`ingestion/retriever.py` ships two interchangeable index backends behind
one interface (`.query()`, `.top_concepts()`, `.save()`, `.load()`):

- **`TfidfIndex`** (`EMBEDDING_BACKEND=tfidf`, default) — TF-IDF + cosine
  similarity. Needs no model download, no GPU, no external service, fully
  deterministic and inspectable for a judge/grader. This is the "runs
  anywhere, zero setup" path.
- **`DenseIndex`** (`EMBEDDING_BACKEND=dense`) — sentence-transformers
  (`all-MiniLM-L6-v2`) embeddings indexed in **FAISS**, a genuine vector
  database. This is what satisfies the "Vector databases" line item under
  the assessment's Technology section, and it recalls by meaning rather
  than shared keywords — e.g. a query like "how current changes with
  resistance" matches a chunk that only says "Ohm's Law" and never uses
  the word "current," which TF-IDF cannot do.

`app.py` calls `load_index()`, which reads a small `backend.txt` marker
written alongside each session's index so it always deserializes with the
backend that actually built it — a session doesn't break if the env var
changes between requests. If `EMBEDDING_BACKEND=dense` is set but
`sentence-transformers`/`faiss-cpu` aren't installed (or the first-run
model download has no internet access), `build_index()` logs why and
falls back to `TfidfIndex` rather than crashing the upload endpoint.

## Why a simple 2D avatar instead of a photoreal talking head

Photoreal talking-head generation (D-ID, HeyGen, Synthesia, or self-hosted
SadTalker/Wav2Lip) needs either a paid API key or a GPU-backed model
server — neither of which should be a prerequisite for a judge to see the
pipeline work. `media/avatar.py` renders an original, simple 2D vector
avatar with a two-frame mouth toggle as a stand-in, wired through the exact
same call site (`media/slides.py::render_slide(mouth_open=...)`) that a
production avatar would use.

**To upgrade**: replace the body of `render_avatar()` with a call to your
chosen provider's image/video API, and in `video_builder.py` replace the
per-section image-sequence + ffmpeg assembly with that provider's talking
video output composited under the same slide/caption layer. Nothing in
`app.py`, `lesson_planner.py`, or the frontend needs to change — video
generation is fully encapsulated behind `build_lesson_video(lesson, out_path)`.

## Why a pluggable TTS chain instead of one hard-coded provider

Requirement #8 asks for multilingual voice; different providers have very
different language coverage and cost. `media/tts.py::narrate()` tries, in
order: ElevenLabs (best multilingual quality) → Azure Neural TTS → gTTS
(free, needs internet) → pyttsx3 (fully offline) → a silence track sized to
the estimated reading time of the narration text (so the video's pacing and
captions are still correct even with zero audio dependencies installed).

## Adaptive teaching loop (requirements #11, #12)

```
checkpoint question ──► student answer ──► adaptive_engine.evaluate_answer()
                                                     │
                              ┌──────────────────────┼───────────────────────┐
                              ▼                                              ▼
                     correctness == "correct"                correctness in {"partial","incorrect"}
                              │                                              │
                              ▼                                              ▼
                     action = "advance"                   misconception_detected = True
                                                            action = "reexplain_with_new_analogy"
                                                                     │
                                                                     ▼
                                                     adaptive_engine.reexplain()
                                                (explicitly told: use a DIFFERENT
                                                 analogy, address the misconception,
                                                 ask a new followup question)
```

This is enforced at the prompt level (`adaptive_engine.py`'s system prompt
tells the model not to paraphrase the previous explanation) and is the
direct implementation of section 12 of the assessment ("Misconception
Detection and Adaptive Teaching").

## Data persistence

- **Per-session document index**: `backend/data/sessions/<session_id>/index.pkl` + `raw_text.txt`
- **Generated lessons/quizzes**: mirrored to `backend/data/sessions/lesson_<id>.json` / `quiz_<id>.json` for inspection/debugging (in-memory dicts in `app.py` are the source of truth at runtime)
- **Generated videos**: `backend/data/videos/<lesson_id>.mp4`
- **Student learning profiles**: `backend/data/profiles.db` (SQLite, one row per completed quiz, aggregated by `teaching/profile_store.py::get_profile()`)

None of this data is committed to the repository (see `.gitignore`) — only the code and one illustrative `sample_output/demo_lesson.mp4` are.

## Speech-to-text for voice answers

`media/stt.py` transcribes a student's recorded checkpoint answer with
**faster-whisper** (CPU, `int8`, offline, no key — model size configurable
via `WHISPER_MODEL_SIZE`), or the hosted OpenAI Whisper API if
`OPENAI_API_KEY` is set. The frontend (`static/app.js::toggleVoiceAnswer`)
records with `MediaRecorder`, posts the blob to
`POST /api/lesson/<id>/answer/audio`, and the transcript is fed into the
exact same `adaptive_engine.evaluate_answer()` path a typed answer uses —
so misconception detection and re-explanation work identically regardless
of input mode. A failed transcription returns a clear error to the UI
rather than silently scoring an empty string as a wrong answer.

## Computer Vision for image-only content

`ingestion/vision.py` handles the material a pure-text extractor misses:

- **DOCX/PPTX**: every embedded picture is pulled straight from the file's
  image relationships/shapes and OCR'd with **Tesseract**
  (`pytesseract.image_to_string`) — python-docx/python-pptx never read
  text out of images at all, so without this step a diagram with labeled
  parts or a formula pasted in as a picture is invisible to the RAG index.
- **PDF**: each page's native-text length is checked; a page with little
  or no extractable text (i.e. probably a scanned image) is rendered at
  200dpi via `pdfplumber`'s pypdfium2 backend and OCR'd. Pages that
  already have real text are left alone, so normal text-native PDFs pay
  no OCR cost.

OCR output is folded into the same `extract_text()` string the chunker
already consumes, tagged `[Image - OCR]` / `[Page N - OCR from
image/diagram]` so it's traceable in `raw_text.txt` per session. A missing
Tesseract binary or any OCR failure logs a warning and degrades to
text-only extraction rather than failing the upload.
