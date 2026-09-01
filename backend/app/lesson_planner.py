"""
Step 1c — Lesson Plan Generation
Turns (topic OR uploaded material) + learner preferences into a structured,
adaptive lesson plan the rest of the pipeline (explanation/video/quiz
generators, built in later steps) will consume.
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict
from typing import List, Optional

import anthropic
from dotenv import load_dotenv

from .rag import MaterialStore

load_dotenv()

_client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
_MODEL = "claude-sonnet-4-6"


@dataclass
class LearnerProfile:
    level: str = "beginner"          # beginner | intermediate | advanced
    language: str = "English"
    available_minutes: int = 20
    learning_objective: Optional[str] = None
    preferred_style: Optional[str] = None  # e.g. "simple examples", "exam-focused"


@dataclass
class LessonSection:
    title: str
    goal: str
    depth: str                # how deep to go, in plain language
    suggested_visual: str     # e.g. "diagram", "equation", "code", "timeline"
    checkpoint_question: Optional[str]  # question to ask student after this section
    grounded_in_material: bool


@dataclass
class LessonPlan:
    topic: str
    learner: LearnerProfile
    total_estimated_minutes: int
    sections: List[LessonSection]
    final_assessment_focus: List[str]


_SYSTEM_PROMPT = """You are the lesson-planning module of an AI Teacher system.
Given a topic, optional grounding material excerpts, and a learner profile,
produce a structured lesson plan as a real teacher would — NOT a list of facts.

Rules:
- Break the lesson into sections that build on each other (understand -> explain -> demonstrate -> question).
- Depth and number of sections must match the learner's available time and level.
  Rough guide: 5 min = 1-2 sections, 20 min = 3-5 sections, 60 min = 6-10 sections.
- Every section needs a checkpoint_question EXCEPT purely introductory sections — questions should test
  understanding, not just recall.
- Pick suggested_visual based on subject matter (equation/graph for math, diagram for processes,
  code for programming, timeline/map for history, labeled diagram for biology, etc).
- If grounding material excerpts are provided, prefer concepts and examples that actually appear in them,
  and set grounded_in_material=true for those sections. Otherwise use your own knowledge and set it false.
- Respond with ONLY valid JSON matching this schema, no preamble, no markdown fences:

{
  "topic": string,
  "total_estimated_minutes": number,
  "sections": [
    {
      "title": string,
      "goal": string,
      "depth": string,
      "suggested_visual": string,
      "checkpoint_question": string or null,
      "grounded_in_material": boolean
    }
  ],
  "final_assessment_focus": [string]
}
"""


def _build_user_prompt(
    topic: str,
    learner: LearnerProfile,
    context_chunks: List[dict],
) -> str:
    parts = [
        f"Topic / instruction from student: {topic}",
        f"Learner level: {learner.level}",
        f"Teaching language: {learner.language}",
        f"Available time: {learner.available_minutes} minutes",
    ]
    if learner.learning_objective:
        parts.append(f"Learning objective: {learner.learning_objective}")
    if learner.preferred_style:
        parts.append(f"Preferred style: {learner.preferred_style}")

    if context_chunks:
        parts.append("\nGrounding material excerpts (from the student's uploaded document):")
        for i, c in enumerate(context_chunks, start=1):
            parts.append(f"[{i}] ({c['source']}, {c['location']}): {c['text']}")
    else:
        parts.append("\nNo uploaded material — teach from general knowledge.")

    return "\n".join(parts)


def generate_lesson_plan(
    topic: str,
    learner: LearnerProfile,
    material_store: Optional[MaterialStore] = None,
) -> LessonPlan:
    """
    Core Day-1 deliverable: given a topic/instruction and learner profile,
    retrieve relevant grounding material (if any) and produce a structured plan.
    """
    context_chunks: List[dict] = []
    if material_store is not None and material_store.has_material():
        context_chunks = material_store.retrieve(topic, k=6)

    user_prompt = _build_user_prompt(topic, learner, context_chunks)

    response = _client.messages.create(
        model=_MODEL,
        max_tokens=2000,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = response.content[0].text.strip()
    # defensive: strip accidental code fences
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        raw_text = raw_text.split("\n", 1)[1] if "\n" in raw_text else raw_text
        if raw_text.endswith("json"):
            raw_text = raw_text[:-4]

    data = json.loads(raw_text)

    sections = [LessonSection(**s) for s in data["sections"]]
    return LessonPlan(
        topic=data["topic"],
        learner=learner,
        total_estimated_minutes=data["total_estimated_minutes"],
        sections=sections,
        final_assessment_focus=data["final_assessment_focus"],
    )


def lesson_plan_to_dict(plan: LessonPlan) -> dict:
    d = asdict(plan)
    return d
