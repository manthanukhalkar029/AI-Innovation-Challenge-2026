"""
Step 1d — API layer
Exposes:
  POST /sessions                 -> create a learning session
  POST /sessions/{id}/upload     -> upload material (PDF/DOCX/PPTX/TXT), gets ingested + embedded
  POST /sessions/{id}/plan       -> generate a lesson plan (topic + learner profile)

Run with: uvicorn app.main:app --reload
"""

from __future__ import annotations
import os
import shutil
import uuid
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel

from .ingestion import ingest_file
from .rag import MaterialStore
from .lesson_planner import LearnerProfile, generate_lesson_plan, lesson_plan_to_dict

app = FastAPI(title="AI Teacher — Day 1 API")

UPLOAD_DIR = "./data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# in-memory session registry — fine for a hackathon prototype,
# swap for a real DB if you need persistence across restarts
_sessions: dict[str, MaterialStore] = {}


class CreateSessionResponse(BaseModel):
    session_id: str


class UploadResponse(BaseModel):
    filename: str
    chunks_ingested: int


class PlanRequest(BaseModel):
    topic: str                      # e.g. "Teach me Chapter 4" or "Explain Newton's Laws"
    level: str = "beginner"
    language: str = "English"
    available_minutes: int = 20
    learning_objective: Optional[str] = None
    preferred_style: Optional[str] = None


@app.post("/sessions", response_model=CreateSessionResponse)
def create_session():
    session_id = str(uuid.uuid4())
    _sessions[session_id] = MaterialStore(session_id)
    return CreateSessionResponse(session_id=session_id)


@app.post("/sessions/{session_id}/upload", response_model=UploadResponse)
async def upload_material(session_id: str, file: UploadFile = File(...)):
    store = _sessions.get(session_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Session not found")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in {".pdf", ".docx", ".pptx", ".txt", ".md"}:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    dest_path = os.path.join(UPLOAD_DIR, f"{session_id}_{file.filename}")
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    chunks = ingest_file(dest_path)
    count = store.add_chunks(chunks)

    return UploadResponse(filename=file.filename, chunks_ingested=count)


@app.post("/sessions/{session_id}/plan")
def create_lesson_plan(session_id: str, req: PlanRequest):
    store = _sessions.get(session_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Session not found")

    learner = LearnerProfile(
        level=req.level,
        language=req.language,
        available_minutes=req.available_minutes,
        learning_objective=req.learning_objective,
        preferred_style=req.preferred_style,
    )

    plan = generate_lesson_plan(req.topic, learner, material_store=store)
    return lesson_plan_to_dict(plan)


@app.get("/health")
def health():
    return {"status": "ok"}
