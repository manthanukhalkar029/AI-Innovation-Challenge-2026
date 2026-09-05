#!/usr/bin/env python3
"""
Zero-setup CLI demo: generates a full lesson end-to-end (plan -> video ->
one adaptive Q&A exchange -> quiz -> report) without needing the web UI.
Useful for a quick sanity check or for a grader who wants to see the
pipeline run in one shot.

Usage:
    cd backend && python ../run_demo.py "Newton's Laws of Motion"
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from teaching.lesson_planner import plan_lesson
from teaching.adaptive_engine import evaluate_answer, reexplain
from teaching.assessment import generate_quiz, score_quiz
from teaching.profile_store import record_session, get_profile
from media.video_builder import build_lesson_video
from llm import get_provider


def main():
    topic = sys.argv[1] if len(sys.argv) > 1 else "Newton's Laws of Motion"
    level, minutes, language = "beginner", 10, "English"

    print(f"[LLM backend] {get_provider().name}")
    print(f"\n=== Planning lesson: {topic} ===")
    lesson = plan_lesson(topic, level, minutes, language)
    print(json.dumps({k: v for k, v in lesson.items() if k != "sections"}, indent=2))
    for s in lesson["sections"]:
        print(f"  - {s['title']}  [{s['visual_type']}]")

    print("\n=== Rendering teaching video (this uses ffmpeg, may take a few seconds) ===")
    out_path = os.path.join("backend", "data", "videos", "demo_cli.mp4")
    build_lesson_video(lesson, out_path)
    print(f"Video written to: {out_path}")

    print("\n=== Simulated student answer (intentionally weak) to section 1 ===")
    section = lesson["sections"][0]
    q = section["checkpoint_question"]["prompt"]
    answer = "not sure"
    result = evaluate_answer(q, answer, section["title"], level, language)
    print(json.dumps(result, indent=2))
    if result.get("misconception_detected"):
        print("\n--- Re-explaining with a different analogy ---")
        print(json.dumps(reexplain(section["title"], section["explanation"], level, language), indent=2))

    print("\n=== End-of-lesson quiz ===")
    concepts = [s["title"] for s in lesson["sections"]]
    quiz = generate_quiz(topic, concepts, level, language)
    answers = {q["id"]: 0 for q in quiz["questions"]}  # simulate all-first-option answers
    report = score_quiz(quiz, answers)
    print(json.dumps(report, indent=2))

    record_session("cli_demo_student", topic, level, language, report)
    print("\n=== Learning profile after this session ===")
    print(json.dumps(get_profile("cli_demo_student"), indent=2))


if __name__ == "__main__":
    main()
