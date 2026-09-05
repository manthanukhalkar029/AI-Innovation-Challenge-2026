# Requirement & Evaluation-Rubric Mapping

Point-by-point mapping of this codebase to the numbered sections of the
Round 2 Technical Assessment.

## Mandatory requirements (section 17)

| Requirement | Implemented in |
|---|---|
| Learning from uploaded material or documents | `backend/ingestion/extract.py`, `chunker.py`, `retriever.py` — PDF/DOCX/PPTX/TXT → RAG index; embedded images, diagrams, and scanned pages are also OCR'd via `ingestion/vision.py` |
| Topic-based teaching | `teaching/lesson_planner.py::plan_lesson()` works with `topic` alone, no upload needed |
| AI-generated lesson structure | `plan_lesson()` returns objectives + ordered sections, each with explanation/example/visual/checkpoint |
| Personalized teaching | `level`, `minutes`, `language`, `style` all shape the generated plan; `profile_store.py` personalizes future sessions against past weak/strong concepts |
| Human-like teaching interaction | `teaching/adaptive_engine.py` — evaluate → detect misconception → re-explain with a new analogy → follow-up question, per section, not just Q&A |
| Video-based AI Teacher presentation | `media/video_builder.py` renders an actual `.mp4` per lesson |
| AI voice | `media/tts.py`, pluggable (ElevenLabs/Azure/gTTS/pyttsx3/silent-fallback) |
| Human-like AI avatar | `media/avatar.py`, composited into every slide in `media/slides.py::render_slide()` |
| Multilingual capability | `language` parameter threaded through lesson planning, evaluation, re-explanation, and TTS language codes (`tts.py::LANG_CODES`) |
| Student questioning and assessment | Per-section `checkpoint_question` (answerable by typed text or by voice via `media/stt.py`) + end-of-lesson quiz (`teaching/assessment.py`) |
| Adaptive response to student performance | `adaptive_engine.py::evaluate_answer()` → branches to `advance` / `reexplain_with_new_analogy` / `simplify_further` / `provide_extra_example` |
| Working application/prototype | `backend/app.py` (Flask) + `backend/static/` (frontend) — run with `python app.py` |

## Numbered sections

| # | Section | Where |
|---|---|---|
| 1 | Objective | End-to-end pipeline described above |
| 2 | User scenario ("beginner, 20 min, Hindi, ask questions, test at end") | Exactly the parameter set the UI collects and `plan_lesson()` consumes |
| 3 | Learning material processing | `ingestion/` package; RAG via `retriever.py`; image/diagram/scanned-page OCR via `vision.py` |
| 4 | Topic-based learning | `plan_lesson()` with no `session_id` |
| 5 | Human-like teaching | `adaptive_engine.py` full evaluate/reexplain loop |
| 6 | Personalized teaching | Level/style parameters in every planning + evaluation prompt |
| 7 | Time-based learning | `minutes` parameter scales section count/depth in `lesson_planner.py` (and in the mock provider's own section-count heuristic) |
| 8 | Multilingual teaching | `language` threaded everywhere; `teaching/adaptive_engine.py` explicitly told to keep language context across re-explanation |
| 9 | AI teaching video | `media/video_builder.py` |
| 10 | Subject-aware visual explanation | `media/slides.py` — six distinct render styles chosen by `visual_type` (`equation_graph`, `diagram_simulation`, `labeled_diagram`, `timeline_map`, `code_execution`, `concept_illustration`) |
| 11 | Interactive learning | Per-section checkpoint questions, answered inline in the UI mid-lesson — by typed text or, via `media/stt.py` (faster-whisper), by voice |
| 12 | Misconception detection & adaptive teaching | `adaptive_engine.py::evaluate_answer()` + `reexplain()` |
| 13 | Assessment and feedback | `teaching/assessment.py::generate_quiz()` + `score_quiz()` |
| 14 | Student learning profile | `teaching/profile_store.py` (SQLite) |
| 15 | AI-generated learning path | `lesson_planner.py::plan_learning_path()`, `/api/lesson/path` |
| 16 | Technology disclosure | See README "Third-party services and libraries disclosed" |
| 18 | Advanced features attempted | Multilingual support, learning-path generation, persistent cross-session profile, subject-aware visuals (6 styles), pluggable everything (LLM/TTS/avatar) so the project can run fully offline or fully production-grade with no code changes |
| 20 | Submission requirements | This repo (source), `README.md` + `docs/` (documentation), `sample_output/demo_lesson.mp4` (proof of a working prototype), see README "Deployment" for hosting |

## Scoring rubric (section 19 table) — self-assessment

| Area | Weight | How this project addresses it |
|---|---|---|
| Human-Like Teaching and Adaptation | 20% | Full evaluate → diagnose misconception → re-explain-with-new-analogy → follow-up loop per checkpoint, not just correct/incorrect marking; the student can answer by voice (`media/stt.py`, `/api/lesson/<id>/answer/audio`) so the interaction resembles talking with a tutor rather than filling a form |
| AI/ML and LLM Implementation | 15% | Model-agnostic `LLMProvider` abstraction; real generative quality the moment a key is supplied; every planning/evaluation/grading step is LLM-driven |
| RAG and Knowledge Grounding | 15% | Chunking + retrieval (TF-IDF by default, or a FAISS vector database with sentence-transformers embeddings via `EMBEDDING_BACKEND=dense`); lesson sections built from uploaded material are explicitly instructed not to invent facts outside retrieved context |
| AI Teaching Video Generation | 15% | Real `.mp4` output per lesson: subject-aware diagrams, talking avatar, captions, narration — see `sample_output/demo_lesson.mp4` |
| Multilingual Capability | 10% | Language parameter end-to-end incl. TTS language codes; **honest limitation**: offline mock mode cannot translate (see README limitations) — real translation requires an LLM key |
| Voice and AI Avatar | 10% | Working avatar+voice pipeline; **honest limitation**: avatar is an original simple 2D illustration, not photoreal — documented upgrade path to D-ID/HeyGen in `docs/ARCHITECTURE.md` |
| Innovation and Originality | 5% | Zero-API-key runnable demo mode + one-line upgrade path to production models is the core design idea, not an afterthought |
| User Experience and Interface | 5% | Single-page, no-build-step frontend covering the full flow: upload → plan → video → interactive Q&A → quiz → report → profile |
| Documentation and Technical Presentation | 5% | This file + `README.md` + `docs/ARCHITECTURE.md` |

We've deliberately been specific about the two weakest areas (avatar
realism, mock-mode translation) rather than overstating them — the judging
criteria explicitly says a "talking avatar reading a generated script" is
not sufficient, so pretending otherwise would be counterproductive. The
architecture is built so that pointing a real budget at those two areas
(a TTS/avatar API key) requires no code changes.
