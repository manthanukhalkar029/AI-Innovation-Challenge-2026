"""
Persistent student learning profile (requirement #14): topics studied,
scores, weak/strong concepts, and current learning path - so future
sessions can be personalized ("you struggled with Ohm's Law last time,
let's revisit it before moving on").
"""
import json
import os
import sqlite3
import time

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "profiles.db")


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lesson_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            topic TEXT,
            level TEXT,
            language TEXT,
            timestamp REAL,
            score_percent INTEGER,
            strong_areas TEXT,
            weak_areas TEXT,
            next_topic TEXT
        )
    """)
    return conn


def record_session(student_id: str, topic: str, level: str, language: str,
                    report: dict):
    conn = _connect()
    conn.execute(
        "INSERT INTO lesson_history (student_id, topic, level, language, "
        "timestamp, score_percent, strong_areas, weak_areas, next_topic) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (student_id, topic, level, language, time.time(),
         report.get("score_percent"),
         json.dumps(report.get("strong_areas", [])),
         json.dumps(report.get("weak_areas", [])),
         report.get("suggested_next_topic")),
    )
    conn.commit()
    conn.close()


def get_profile(student_id: str) -> dict:
    conn = _connect()
    rows = conn.execute(
        "SELECT topic, level, language, timestamp, score_percent, "
        "strong_areas, weak_areas, next_topic FROM lesson_history "
        "WHERE student_id = ? ORDER BY timestamp DESC", (student_id,)
    ).fetchall()
    conn.close()

    history = []
    weak_all, strong_all = [], []
    for r in rows:
        weak = json.loads(r[6] or "[]")
        strong = json.loads(r[5] or "[]")
        weak_all.extend(weak)
        strong_all.extend(strong)
        history.append({
            "topic": r[0], "level": r[1], "language": r[2],
            "timestamp": r[3], "score_percent": r[4],
            "strong_areas": strong, "weak_areas": weak, "next_topic": r[7],
        })

    return {
        "student_id": student_id,
        "topics_studied": list({h["topic"] for h in history if h["topic"]}),
        "session_count": len(history),
        "weak_concepts": list(dict.fromkeys(weak_all)),   # de-duped, order kept
        "strong_concepts": list(dict.fromkeys(strong_all)),
        "recommended_next": history[0]["next_topic"] if history else None,
        "history": history,
    }
