"""
Turns (uploaded material | topic) + learner profile into a structured lesson.

This is the "planning" step of human-like teaching: a real teacher does not
start talking immediately - they decide what to cover, in what order, how
deep, and with what examples, before the lesson begins. That plan is what
gets rendered into slides/video in media/video_builder.py and driven step by
step by teaching/adaptive_engine.py.
"""
import json
from llm import get_provider


def plan_lesson(topic: str, level: str, minutes: int, language: str,
                 style: str = "balanced", context_chunks=None) -> dict:
    provider = get_provider()
    payload = {
        "topic": topic,
        "level": level,
        "minutes": minutes,
        "language": language,
        "style": style,
        "context": context_chunks or [],
    }
    system = (
        "You are an expert curriculum designer and master teacher. You design "
        "a structured, personalized lesson plan the way a real human tutor "
        "would prepare before a 1-on-1 session: pick what to teach first, how "
        "deep to go, which examples fit the learner's level, where to check "
        "understanding, and which kind of visual best explains each idea "
        "(equation_graph, diagram_simulation, labeled_diagram, timeline_map, "
        "code_execution, or concept_illustration). "
        "If 'context' chunks are provided, ground every section in that "
        "material and do not invent facts not supported by it. "
        "Respond as JSON with this exact shape: {\"title\": str, \"level\": str, "
        "\"language\": str, \"duration_minutes\": int, \"objectives\": [str], "
        "\"sections\": [{\"title\": str, \"explanation\": str, \"example\": str, "
        "\"visual_type\": str, \"checkpoint_question\": {\"type\": str, \"prompt\": str}}]}. "
        f"Write all lesson content in {language}. Adjust vocabulary and depth "
        f"for a '{level}' learner. Fit the whole lesson inside {minutes} minutes: "
        "fewer, deeper sections for short lessons; more sections with practice "
        "and assessment for long ones."
    )
    prompt = (
        f"### TASK: lesson_plan\n"
        f"### PAYLOAD: {json.dumps(payload)}\n"
        f"Design the lesson now."
    )
    plan = provider.complete_json(system, prompt, max_tokens=2500)
    plan.setdefault("provider_used", provider.name)
    return plan


def plan_learning_path(topic: str, context_chunks=None) -> dict:
    """For broad topics: a multi-module curriculum, e.g. Machine Learning ->
    Python Fundamentals -> Math for ML -> ... -> Advanced ML."""
    provider = get_provider()
    payload = {"topic": topic, "context": context_chunks or []}
    system = (
        "You are a curriculum architect. Break a broad subject into an "
        "ordered sequence of learning modules a beginner could follow start "
        "to finish, each buildable on the last. Respond as JSON: "
        "{\"topic\": str, \"modules\": [{\"title\": str, \"why\": str}]}"
    )
    prompt = f"### TASK: learning_path\n### PAYLOAD: {json.dumps(payload)}\nBuild the path."
    try:
        return provider.complete_json(system, prompt, max_tokens=1200)
    except Exception:
        return {"topic": topic, "modules": [{"title": topic, "why": "starting point"}]}
