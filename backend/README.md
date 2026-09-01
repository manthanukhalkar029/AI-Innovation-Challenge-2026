# AI Teacher — Backend (Day 1: Ingestion + RAG + Lesson Planning)

This is the first working slice of the AI Teacher project: it can take an
uploaded document (or just a topic) and turn it into a structured,
personalized lesson plan — the "Understand → Plan" part of the pipeline.

## What's included

- `app/ingestion.py` — parses PDF / DOCX / PPTX / TXT into clean text chunks
- `app/rag.py` — embeds chunks (local model, free) and stores them in Chroma for retrieval
- `app/lesson_planner.py` — calls Claude to turn topic + learner profile + retrieved material into a structured lesson plan
- `app/main.py` — FastAPI endpoints tying it together

## Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env and add your ANTHROPIC_API_KEY
```

## Run

```bash
uvicorn app.main:app --reload
```

Server starts at `http://localhost:8000`. Interactive docs at
`http://localhost:8000/docs`.

## Try it end-to-end

```bash
# 1. Create a session
curl -X POST http://localhost:8000/sessions
# -> {"session_id": "..."}

# 2. Upload material (optional — you can skip straight to step 3 for topic-only teaching)
curl -X POST http://localhost:8000/sessions/<session_id>/upload \
  -F "file=@/path/to/chapter4.pdf"

# 3. Generate a lesson plan
curl -X POST http://localhost:8000/sessions/<session_id>/plan \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Teach me Chapter 4 in 20 minutes, explain it simply",
    "level": "beginner",
    "language": "English",
    "available_minutes": 20
  }'
```

You'll get back a JSON lesson plan: an ordered list of sections, each with
a goal, depth, a suggested visual type (equation/diagram/code/etc — this
feeds Day 2's explanation + visual generator), and a checkpoint question
(this feeds Day 4's interaction loop).

## Notes

- Uses `all-MiniLM-L6-v2` for embeddings (free, runs locally, no API cost).
- Chroma persists to `./data/chroma` — delete that folder to reset all sessions.
- Sessions are in-memory (`_sessions` dict in `main.py`) — fine for a hackathon
  demo, but they reset if the server restarts. Swap for Postgres/SQLite if you
  need persistence.
- Model is set to `claude-sonnet-4-6` — adjust if you're on a different tier.

## Next steps (Day 2+)

- `app/explainer.py` — turn each lesson section into a spoken script + pick/generate the actual visual (matplotlib for math, mermaid for diagrams, etc.)
- TTS integration (Coqui/edge-tts) for multilingual voice
- SadTalker/Wav2Lip for avatar video generation
- ffmpeg compositing pipeline
