"""
The "does the student actually understand this" loop.

Real teaching isn't linear: after each checkpoint question the teacher
decides whether to advance, re-explain with a new analogy, simplify, or go
deeper. This module makes that decision and generates the branch content,
which is exactly requirement #12 (Misconception Detection and Adaptive
Teaching) and #11 (Interactive Learning).
"""
import json
from llm import get_provider


def evaluate_answer(question: str, student_answer: str, reference_concept: str,
                     level: str = "beginner", language: str = "English") -> dict:
    provider = get_provider()
    payload = {
        "question": question,
        "answer": student_answer,
        "reference_concept": reference_concept,
        "level": level,
        "language": language,
    }
    system = (
        "You are a patient, encouraging human tutor grading a student's spoken "
        "or typed answer during a live lesson. Do not just mark right/wrong: "
        "diagnose *why* an incorrect or partial answer is wrong (the specific "
        "misconception), and decide the pedagogical next move. "
        "Respond as JSON: {\"correctness\": \"correct\"|\"partial\"|\"incorrect\"|"
        "\"unattempted\", \"feedback\": str, \"misconception_detected\": bool, "
        "\"misconception_explanation\": str, \"action\": \"advance\"|"
        "\"reexplain_with_new_analogy\"|\"simplify_further\"|\"provide_extra_example\"}. "
        f"Write feedback in {language}, appropriate for a {level} learner."
    )
    prompt = f"### TASK: evaluate_answer\n### PAYLOAD: {json.dumps(payload)}\nEvaluate now."
    return provider.complete_json(system, prompt, max_tokens=600)


def reexplain(concept: str, previous_explanation: str, level: str,
              language: str, misconception: str = "") -> dict:
    """Generates a fresh explanation using a *different* analogy - never repeats
    the same wording the student already didn't understand."""
    provider = get_provider()
    payload = {
        "concept": concept,
        "previous_explanation": previous_explanation,
        "misconception": misconception,
        "level": level,
        "language": language,
    }
    system = (
        "You are re-teaching a concept the student struggled with. Use a "
        "genuinely different analogy or approach than the previous "
        "explanation - do not paraphrase it. Directly address the "
        "misconception if one was identified. "
        "Respond as JSON: {\"explanation\": str, \"new_example\": str, "
        "\"followup_question\": str}."
        f" Write in {language} at a {level} level."
    )
    prompt = f"### TASK: reexplain\n### PAYLOAD: {json.dumps(payload)}\nRe-teach it."
    try:
        return provider.complete_json(system, prompt, max_tokens=700)
    except Exception:
        return {
            "explanation": f"Let's look at {concept} from a different angle, "
                            f"one step at a time.",
            "new_example": f"Picture {concept} as a small, everyday routine "
                            f"broken into its individual steps.",
            "followup_question": f"Now, can you describe {concept} in one sentence?",
        }
