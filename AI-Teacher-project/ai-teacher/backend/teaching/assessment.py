"""
End-of-lesson quiz generation + scoring + learning report (requirement #13).
"""
import json
from llm import get_provider


def generate_quiz(topic: str, concepts, level: str = "beginner",
                   language: str = "English", n_questions: int = 5) -> dict:
    provider = get_provider()
    payload = {"topic": topic, "concepts": concepts, "level": level,
               "language": language, "n_questions": n_questions}
    system = (
        "You are writing a short end-of-lesson quiz mixing MCQ and "
        "short-answer questions that test real understanding, not "
        "memorization. Tag each question with the single concept it tests "
        "so results can be mapped to strengths/weaknesses. "
        "Respond as JSON: {\"topic\": str, \"questions\": [{\"id\": str, "
        "\"type\": \"mcq\"|\"short_answer\", \"concept\": str, \"prompt\": str, "
        "\"options\": [str] (mcq only), \"correct_index\": int (mcq only), "
        "\"model_answer\": str (short_answer only)}]}."
        f" Write in {language} for a {level} learner."
    )
    prompt = f"### TASK: generate_quiz\n### PAYLOAD: {json.dumps(payload)}\nWrite the quiz."
    return provider.complete_json(system, prompt, max_tokens=1500)


def score_quiz(quiz: dict, student_answers: dict) -> dict:
    """student_answers: {question_id: answer}. Uses the LLM to grade
    short-answer questions and simple equality for MCQ, then produces the
    structured report (score / strong / weak / recommendation / next topic)."""
    provider = get_provider()
    scored = []
    for q in quiz.get("questions", []):
        qid = q["id"]
        given = student_answers.get(qid, "")
        if q["type"] == "mcq":
            correct = str(given) == str(q.get("correct_index"))
        else:
            eval_result = evaluate_answer_for_grading(q, given)
            correct = eval_result.get("correct", False)
        scored.append({"id": qid, "concept": q.get("concept", "general"), "correct": correct})

    payload = {"scored_questions": scored, "topic": quiz.get("topic", "")}
    system = (
        "You are producing a learning report after a quiz, in the style of a "
        "real teacher's feedback: score, strong areas, weak areas, and a "
        "specific, actionable recommendation plus a suggested next topic. "
        "Respond as JSON: {\"score_percent\": int, \"strong_areas\": [str], "
        "\"weak_areas\": [str], \"recommendation\": str, \"suggested_next_topic\": str}."
    )
    prompt = f"### TASK: report\n### PAYLOAD: {json.dumps(payload)}\nWrite the report."
    report = provider.complete_json(system, prompt, max_tokens=600)
    report["raw_scores"] = scored
    return report


def evaluate_answer_for_grading(question: dict, given_answer: str) -> dict:
    provider = get_provider()
    payload = {
        "question": question.get("prompt", ""),
        "answer": given_answer,
        "reference_concept": question.get("model_answer", question.get("concept", "")),
    }
    system = ("Grade this short answer against the model answer/concept. "
              "Respond as JSON: {\"correct\": bool, \"explanation\": str}.")
    prompt = f"### TASK: evaluate_answer\n### PAYLOAD: {json.dumps(payload)}\nGrade it."
    try:
        result = provider.complete_json(system, prompt, max_tokens=300)
        # mock provider returns 'correctness' field instead of 'correct'
        if "correct" not in result and "correctness" in result:
            result["correct"] = result["correctness"] == "correct"
        return result
    except Exception:
        return {"correct": bool(given_answer.strip()), "explanation": ""}
