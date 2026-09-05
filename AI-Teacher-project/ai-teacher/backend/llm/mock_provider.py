"""
Offline, zero-dependency, zero-API-key provider.

Why this exists: hackathon judges often clone dozens of repos and don't want
to hunt for API keys before they can see anything work. Every teaching
module in this project talks to the LLM through a "### TASK: <name>" header
followed by a JSON payload of inputs. Real LLM providers just read that as
part of natural-language instructions and produce a good answer. This mock
provider *parses* the same header/payload and synthesizes a reasonable,
deterministic answer using simple extractive NLP (sentence scoring, keyword
templates) - no network, no model weights, runs anywhere Python runs.

It is intentionally simple. It exists to make the full pipeline runnable and
demoable end-to-end with zero setup; swapping in ANTHROPIC_API_KEY or
OPENAI_API_KEY immediately upgrades every lesson, explanation, and
evaluation to real generative quality without any code changes elsewhere.
"""
import json
import re
import textwrap
from .base import LLMProvider


def _sentences(text: str):
    text = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if len(p.strip()) > 20]


def _keywords(text: str, n=6):
    words = re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text)
    stop = {"this", "that", "with", "from", "have", "which", "there", "their",
            "about", "into", "your", "would", "these", "those", "such", "than"}
    freq = {}
    for w in words:
        lw = w.lower()
        if lw in stop:
            continue
        freq[lw] = freq.get(lw, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:n]]


LEVEL_TONE = {
    "beginner": "in simple, everyday language with a relatable analogy",
    "intermediate": "with clear technical language and a practical example",
    "advanced": "with precise terminology, underlying mechanisms, and edge cases",
}


class MockProvider(LLMProvider):
    name = "mock (offline demo mode)"

    def complete(self, system: str, prompt: str, json_mode: bool = False,
                 max_tokens: int = 1500, temperature: float = 0.4) -> str:
        task_match = re.search(r"###\s*TASK:\s*(\w+)", prompt)
        task = task_match.group(1) if task_match else "generic"
        payload = {}
        for line in prompt.splitlines():
            line = line.strip()
            if line.startswith("### PAYLOAD:"):
                raw = line[len("### PAYLOAD:"):].strip()
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    # payload JSON spilled onto more than one line (rare,
                    # e.g. very long context) - fall back to a greedy scan.
                    match = re.search(r"(\{.*\})", prompt, re.DOTALL)
                    if match:
                        try:
                            payload = json.loads(match.group(1))
                        except json.JSONDecodeError:
                            payload = {}
                break

        handler = getattr(self, f"_task_{task}", self._task_generic)
        result = handler(payload)
        return json.dumps(result) if json_mode else json.dumps(result)

    # ---- task handlers -------------------------------------------------

    def _task_lesson_plan(self, p):
        topic = p.get("topic", "the requested topic")
        level = p.get("level", "beginner")
        minutes = p.get("minutes", 20)
        context_chunks = p.get("context", [])
        source_text = " ".join(context_chunks) if context_chunks else ""
        sents = _sentences(source_text)
        kws = _keywords(source_text or topic, n=8) or [topic]

        n_sections = max(2, min(6, minutes // 7))
        sections = []
        pool = sents if sents else [
            f"{topic} is built on a small set of core ideas that connect to each other."
            for _ in range(n_sections)
        ]
        chunk_size = max(1, len(pool) // n_sections) if pool else 1

        for i in range(n_sections):
            kw = kws[i % len(kws)]
            evidence = pool[i * chunk_size:(i + 1) * chunk_size] or pool[:1]
            explanation = " ".join(evidence)[:600] if evidence else (
                f"{kw.capitalize()} is a key idea within {topic}, explained "
                f"{LEVEL_TONE.get(level, LEVEL_TONE['beginner'])}."
            )
            sections.append({
                "title": f"{i+1}. {kw.capitalize()}" if source_text else f"{i+1}. {topic} - Part {i+1}",
                "explanation": explanation,
                "example": f"Think of {kw} the way you'd think of a familiar, everyday process - "
                           f"break it into the smallest step, then build back up to the full idea.",
                "visual_type": _guess_visual_type(topic + " " + kw),
                "checkpoint_question": {
                    "type": "short_answer",
                    "prompt": f"In your own words, what is the role of '{kw}' in {topic}?",
                }
            })

        return {
            "title": f"Lesson: {topic}",
            "level": level,
            "language": p.get("language", "English"),
            "duration_minutes": minutes,
            "objectives": [f"Understand {kw}" for kw in kws[:4]] or [f"Understand {topic}"],
            "sections": sections,
            "provider_note": "Generated by offline mock provider - set ANTHROPIC_API_KEY or "
                              "OPENAI_API_KEY for full generative-quality lessons.",
        }

    def _task_evaluate_answer(self, p):
        question = p.get("question", "")
        answer = (p.get("answer", "") or "").strip()
        reference = p.get("reference_concept", "")
        kws = set(_keywords(question + " " + reference, n=10))
        answer_kws = set(w.lower() for w in re.findall(r"[A-Za-z]{4,}", answer))
        overlap = kws & answer_kws
        if not answer:
            correctness = "unattempted"
        elif len(overlap) >= max(1, len(kws) // 3):
            correctness = "correct"
        elif len(answer) > 0:
            correctness = "partial"
        else:
            correctness = "incorrect"

        feedback = {
            "correct": "Yes, that's right - you've connected the key idea correctly.",
            "partial": "You're on the right track, but the explanation is incomplete. "
                       "Let's go over the missing piece.",
            "incorrect": "That's a common misconception - let's re-examine this with a "
                         "different example.",
            "unattempted": "No answer given - let's walk through it together first.",
        }[correctness]

        return {
            "correctness": correctness,
            "feedback": feedback,
            "misconception_detected": correctness in ("incorrect", "partial"),
            "action": "advance" if correctness == "correct" else "reexplain_with_new_analogy",
        }

    def _task_reexplain(self, p):
        concept = p.get("concept", "this idea")
        level = p.get("level", "beginner")
        return {
            "explanation": f"Let's try {concept} a different way. "
                            f"{LEVEL_TONE.get(level, LEVEL_TONE['beginner']).capitalize()}, "
                            f"picture it as a chain of cause and effect: one small change "
                            f"at the start leads directly to the result you observed.",
            "new_example": f"Imagine explaining {concept} to a friend using only something "
                            f"from daily life - no jargon, just the underlying cause and effect.",
            "followup_question": f"Now try again: what happens to the outcome if the "
                                  f"starting condition in {concept} changes?",
        }

    def _task_generate_quiz(self, p):
        topic = p.get("topic", "the topic")
        concepts = p.get("concepts", [topic])
        questions = []
        for i, c in enumerate(concepts[:6]):
            questions.append({
                "id": f"q{i+1}",
                "type": "mcq",
                "concept": c,
                "prompt": f"Which statement best describes '{c}' in the context of {topic}?",
                "options": [
                    f"It is a core mechanism behind {c}.",
                    f"It is unrelated to {topic}.",
                    f"It only applies outside of {topic}.",
                    "None of the above.",
                ],
                "correct_index": 0,
            })
        return {"topic": topic, "questions": questions}

    def _task_translate(self, p):
        # Mock mode cannot truly translate; it labels content clearly so the
        # limitation is transparent rather than silently wrong.
        text = p.get("text", "")
        lang = p.get("target_language", "the target language")
        return {"translated_text": text,
                "note": f"[offline mock mode cannot translate to {lang} - "
                        f"connect a real LLM provider for multilingual output]"}

    def _task_report(self, p):
        scored = p.get("scored_questions", [])
        total = len(scored) or 1
        correct = sum(1 for q in scored if q.get("correct"))
        pct = round(100 * correct / total)
        weak = [q["concept"] for q in scored if not q.get("correct")]
        strong = [q["concept"] for q in scored if q.get("correct")]
        return {
            "score_percent": pct,
            "strong_areas": strong,
            "weak_areas": weak,
            "recommendation": f"Revise {', '.join(weak) or 'nothing - great job'} "
                               f"and try two more practice questions on each.",
            "suggested_next_topic": p.get("topic", "the next module in the learning path"),
        }

    def _task_generic(self, p):
        return {"note": "mock provider: no handler for this task", "payload": p}


def _guess_visual_type(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["equation", "algebra", "calculus", "math", "geometry"]):
        return "equation_graph"
    if any(k in t for k in ["circuit", "force", "physics", "energy", "motion"]):
        return "diagram_simulation"
    if any(k in t for k in ["cell", "biology", "organ", "anatomy", "gene"]):
        return "labeled_diagram"
    if any(k in t for k in ["history", "war", "century", "empire", "revolution", "timeline"]):
        return "timeline_map"
    if any(k in t for k in ["code", "program", "function", "algorithm", "python", "react", "api"]):
        return "code_execution"
    return "concept_illustration"
