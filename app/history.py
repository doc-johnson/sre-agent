import json
import sqlite3
from datetime import datetime, timezone

from app.config import DB_PATH


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS investigations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert TEXT NOT NULL,
            conclusion TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS investigation_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            investigation_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            data TEXT NOT NULL,
            seq INTEGER NOT NULL,
            FOREIGN KEY (investigation_id) REFERENCES investigations(id)
        )
    """)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()
    return conn


def save_investigation(alert: str, conclusion: str, events: list[dict]) -> int:
    conn = _conn()
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO investigations (alert, conclusion, created_at) VALUES (?, ?, ?)",
        (alert, conclusion, now),
    )
    inv_id = cur.lastrowid
    for i, event in enumerate(events):
        conn.execute(
            "INSERT INTO investigation_events (investigation_id, event_type, data, seq) VALUES (?, ?, ?, ?)",
            (inv_id, event.get("type", ""), json.dumps(event, default=str), i),
        )
    conn.commit()
    conn.close()
    return inv_id


def list_investigations() -> list[dict]:
    conn = _conn()
    rows = conn.execute(
        "SELECT id, alert, conclusion, created_at FROM investigations ORDER BY id DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return [
        {"id": r[0], "alert": r[1], "conclusion": r[2], "created_at": r[3]}
        for r in rows
    ]


def get_investigation(inv_id: int) -> dict | None:
    conn = _conn()
    row = conn.execute(
        "SELECT id, alert, conclusion, created_at FROM investigations WHERE id = ?",
        (inv_id,),
    ).fetchone()
    if not row:
        conn.close()
        return None
    events = conn.execute(
        "SELECT event_type, data FROM investigation_events WHERE investigation_id = ? ORDER BY seq",
        (inv_id,),
    ).fetchall()
    conn.close()
    return {
        "id": row[0],
        "alert": row[1],
        "conclusion": row[2],
        "created_at": row[3],
        "events": [{"type": e[0], "data": json.loads(e[1])} for e in events],
    }
