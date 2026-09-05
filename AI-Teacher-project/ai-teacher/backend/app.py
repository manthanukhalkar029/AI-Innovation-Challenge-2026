"""
AI Teacher - Flask backend.

Endpoints implement the full mandatory-requirement flow:
  upload material -> RAG index -> personalized lesson plan -> teaching video
  -> interactive checkpoint Q&A with misconception detection -> end-of-lesson
  quiz -> scored report -> persisted student profile for future sessions.

Run: python backend/app.py   (see README.md for setup)
"""
import json
import os
import uuid

from flask import Flask, jsonify, request, send_from_directory

from ingestion.retriever import build_index, load_index
from teaching.lesson_planner import plan_lesson, plan_learning_path
from teaching.adaptive_engine import evaluate_answer, reexplain
from teaching.assessment import generate_quiz, score_quiz
from teaching.profile_store import record_session, get_profile
from media.video_builder import build_lesson_video
from media.stt import transcribe
from llm import get_provider

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
SESSION_DIR = os.path.join(DATA_DIR, "sessions")
VIDEO_DIR = os.path.join(DATA_DIR, "videos")
STATIC_DIR = os.path.join(BASE_DIR, "static")

for d in (UPLOAD_DIR, SESSION_DIR, VIDEO_DIR):
    os.makedirs(d, exist_ok=True)

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")

_LESSONS = {}   # lesson_id -> lesson dict   (also mirrored to disk)
_QUIZZES = {}   # quiz_id -> quiz dict


def _save_json(directory, obj_id, obj):
    with open(os.path.join(directory, f"{obj_id}.json"), "w") as f:
        json.dump(obj, f, indent=2)


# ---------------------------------------------------------------- frontend
@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/api/status")
def status():
    return jsonify({"ok": True, "llm_provider": get_provider().name})


# ---------------------------------------------------------------- ingestion
@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "no file provided"}), 400
    f = request.files["file"]
    session_id = str(uuid.uuid4())[:8]
    filepath = os.path.join(UPLOAD_DIR, f"{session_id}_{f.filename}")
    f.save(filepath)

    session_dir = os.path.join(SESSION_DIR, session_id)
    index = build_index(filepath, session_dir)

    ocr_chunks = sum(1 for c in index.chunks if "OCR" in c)
    return jsonify({
        "session_id": session_id,
        "filename": f.filename,
        "chunk_count": len(index.chunks),
        "top_concepts": index.top_concepts(10),
        "embedding_backend": index.backend,
        "ocr_chunks_found": ocr_chunks,
    })


def _get_index(session_id: str):
    return load_index(os.path.join(SESSION_DIR, session_id))


# ---------------------------------------------------------------- lesson
@app.route("/api/lesson/plan", methods=["POST"])
def lesson_plan():
    body = request.get_json(force=True)
    topic = body.get("topic", "")
    level = body.get("level", "beginner")
    minutes = int(body.get("minutes", 20))
    language = body.get("language", "English")
    style = body.get("style", "balanced")
    session_id = body.get("session_id")

    context_chunks = []
    if session_id:
        index = _get_index(session_id)
        query = topic or " ".join(index.top_concepts(5))
        context_chunks = [r["chunk"] for r in index.query(query, top_k=6)]
        if not topic:
            topic = index.top_concepts(3)
            topic = ", ".join(topic) if topic else "the uploaded material"

    lesson = plan_lesson(topic, level, minutes, language, style, context_chunks)
    lesson_id = str(uuid.uuid4())[:8]
    lesson["lesson_id"] = lesson_id
    lesson["topic"] = topic
    lesson["session_id"] = session_id
    _LESSONS[lesson_id] = lesson
    _save_json(SESSION_DIR, f"lesson_{lesson_id}", lesson)
    return jsonify(lesson)


@app.route("/api/lesson/path", methods=["POST"])
def lesson_path():
    body = request.get_json(force=True)
    return jsonify(plan_learning_path(body.get("topic", "")))


@app.route("/api/lesson/<lesson_id>", methods=["GET"])
def get_lesson(lesson_id):
    lesson = _LESSONS.get(lesson_id)
    if not lesson:
        return jsonify({"error": "lesson not found"}), 404
    return jsonify(lesson)


@app.route("/api/lesson/<lesson_id>/video", methods=["POST"])
def lesson_video(lesson_id):
    lesson = _LESSONS.get(lesson_id)
    if not lesson:
        return jsonify({"error": "lesson not found"}), 404
    out_path = os.path.join(VIDEO_DIR, f"{lesson_id}.mp4")
    build_lesson_video(lesson, out_path)
    return jsonify({"video_url": f"/api/video/{lesson_id}.mp4"})


@app.route("/api/video/<filename>")
def serve_video(filename):
    return send_from_directory(VIDEO_DIR, filename)


# ---------------------------------------------------------------- interaction
def _evaluate_section_answer(lesson: dict, section_index: int, answer: str) -> dict:
    section = lesson["sections"][section_index]
    question = section["checkpoint_question"]["prompt"]

    result = evaluate_answer(question, answer, section.get("title", ""),
                              lesson.get("level", "beginner"), lesson.get("language", "English"))

    if result.get("action", "").startswith("reexplain") or result.get("misconception_detected"):
        extra = reexplain(section.get("title", ""), section.get("explanation", ""),
                           lesson.get("level", "beginner"), lesson.get("language", "English"),
                           misconception=result.get("misconception_explanation", ""))
        result["reexplanation"] = extra
    return result


@app.route("/api/lesson/<lesson_id>/answer", methods=["POST"])
def lesson_answer(lesson_id):
    lesson = _LESSONS.get(lesson_id)
    if not lesson:
        return jsonify({"error": "lesson not found"}), 404
    body = request.get_json(force=True)
    section_index = int(body.get("section_index", 0))
    answer = body.get("answer", "")

    result = _evaluate_section_answer(lesson, section_index, answer)
    result["answer_text"] = answer
    result["input_mode"] = "text"
    return jsonify(result)


@app.route("/api/lesson/<lesson_id>/answer/audio", methods=["POST"])
def lesson_answer_audio(lesson_id):
    """Same checkpoint-evaluation flow as /answer, but the student speaks
    the answer instead of typing it (Speech-to-Text, section 16 technology
    list) - the recording is transcribed with media/stt.py and the
    resulting text is scored exactly like a typed answer."""
    lesson = _LESSONS.get(lesson_id)
    if not lesson:
        return jsonify({"error": "lesson not found"}), 404
    if "audio" not in request.files:
        return jsonify({"error": "no audio file provided"}), 400

    section_index = int(request.form.get("section_index", 0))
    audio_file = request.files["audio"]
    audio_path = os.path.join(UPLOAD_DIR, f"answer_{uuid.uuid4().hex[:8]}_{audio_file.filename or 'audio.webm'}")
    audio_file.save(audio_path)

    try:
        transcript = transcribe(audio_path, lesson.get("language", "English"))
    except Exception as e:
        return jsonify({"error": str(e)}), 503
    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)

    answer_text = transcript["text"]
    if not answer_text:
        return jsonify({"error": "could not understand the recording - please try again or type your answer"}), 422

    result = _evaluate_section_answer(lesson, section_index, answer_text)
    result["answer_text"] = answer_text
    result["input_mode"] = "voice"
    result["stt_backend"] = transcript["backend"]
    return jsonify(result)


# ---------------------------------------------------------------- assessment
@app.route("/api/quiz/generate", methods=["POST"])
def quiz_generate():
    body = request.get_json(force=True)
    lesson_id = body.get("lesson_id")
    lesson = _LESSONS.get(lesson_id, {})
    topic = lesson.get("topic") or body.get("topic", "the topic")
    concepts = [s["title"] for s in lesson.get("sections", [])] or body.get("concepts", [topic])
    quiz = generate_quiz(topic, concepts, lesson.get("level", body.get("level", "beginner")),
                          lesson.get("language", body.get("language", "English")))
    quiz_id = str(uuid.uuid4())[:8]
    quiz["quiz_id"] = quiz_id
    quiz["lesson_id"] = lesson_id
    _QUIZZES[quiz_id] = quiz
    _save_json(SESSION_DIR, f"quiz_{quiz_id}", quiz)
    return jsonify(quiz)


@app.route("/api/quiz/<quiz_id>/submit", methods=["POST"])
def quiz_submit(quiz_id):
    quiz = _QUIZZES.get(quiz_id)
    if not quiz:
        return jsonify({"error": "quiz not found"}), 404
    body = request.get_json(force=True)
    answers = body.get("answers", {})
    student_id = body.get("student_id", "guest")

    report = score_quiz(quiz, answers)
    lesson = _LESSONS.get(quiz.get("lesson_id"), {})
    record_session(student_id, lesson.get("topic", quiz.get("topic", "")),
                    lesson.get("level", "beginner"), lesson.get("language", "English"), report)
    return jsonify(report)


@app.route("/api/profile/<student_id>")
def profile(student_id):
    return jsonify(get_profile(student_id))


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "0") == "1")
