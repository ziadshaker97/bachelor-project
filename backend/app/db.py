import json
import sqlite3

from .config import DB_PATH, RUNTIME_DIR
from .models import EmployeeProfile


def ensure_runtime() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    ensure_runtime()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                employee_id TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                department TEXT NOT NULL,
                experience_level TEXT NOT NULL,
                known_skills TEXT NOT NULL,
                learning_preferences TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                employee_id TEXT NOT NULL,
                speaker TEXT NOT NULL,
                message TEXT NOT NULL
            )
            """
        )
        conn.commit()


def save_profile(profile: EmployeeProfile) -> bool:
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT employee_id FROM profiles WHERE employee_id = ?",
            (profile.employee_id,),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO profiles (
                employee_id, role, department, experience_level, known_skills, learning_preferences
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(employee_id) DO UPDATE SET
                role = excluded.role,
                department = excluded.department,
                experience_level = excluded.experience_level,
                known_skills = excluded.known_skills,
                learning_preferences = excluded.learning_preferences
            """,
            (
                profile.employee_id,
                profile.role,
                profile.department,
                profile.experience_level,
                json.dumps(profile.known_skills),
                json.dumps(profile.learning_preferences),
            ),
        )
        conn.commit()
    return existing is None


def load_profile(employee_id: str) -> EmployeeProfile | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM profiles WHERE employee_id = ?",
            (employee_id,),
        ).fetchone()
    if row is None:
        return None
    return EmployeeProfile(
        employee_id=row["employee_id"],
        role=row["role"],
        department=row["department"],
        experience_level=row["experience_level"],
        known_skills=json.loads(row["known_skills"]),
        learning_preferences=json.loads(row["learning_preferences"]),
    )


def add_chat_message(session_id: str, employee_id: str, speaker: str, message: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO chat_messages (session_id, employee_id, speaker, message)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, employee_id, speaker, message),
        )
        conn.commit()


def load_chat_history(session_id: str, employee_id: str, limit: int = 6) -> list[dict[str, str]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT speaker, message
            FROM chat_messages
            WHERE session_id = ? AND employee_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, employee_id, limit),
        ).fetchall()
    return [{"speaker": row["speaker"], "message": row["message"]} for row in reversed(rows)]

