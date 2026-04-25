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
                learning_preferences TEXT NOT NULL,
                access_level TEXT NOT NULL DEFAULT 'employee',
                cv_summary TEXT NOT NULL DEFAULT '',
                career_goals TEXT NOT NULL DEFAULT '[]',
                months_in_training INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(profiles)").fetchall()}
        if "access_level" not in columns:
            conn.execute("ALTER TABLE profiles ADD COLUMN access_level TEXT NOT NULL DEFAULT 'employee'")
        if "cv_summary" not in columns:
            conn.execute("ALTER TABLE profiles ADD COLUMN cv_summary TEXT NOT NULL DEFAULT ''")
        if "career_goals" not in columns:
            conn.execute("ALTER TABLE profiles ADD COLUMN career_goals TEXT NOT NULL DEFAULT '[]'")
        if "months_in_training" not in columns:
            conn.execute("ALTER TABLE profiles ADD COLUMN months_in_training INTEGER NOT NULL DEFAULT 0")
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS course_progress (
                employee_id TEXT NOT NULL,
                course_id TEXT NOT NULL,
                status TEXT NOT NULL,
                progress_percent INTEGER NOT NULL,
                saved_for_later INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (employee_id, course_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS module_progress (
                employee_id TEXT NOT NULL,
                module_id TEXT NOT NULL,
                status TEXT NOT NULL,
                progress_percent INTEGER NOT NULL,
                saved_for_later INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (employee_id, module_id)
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
                employee_id, role, department, experience_level, known_skills, learning_preferences, access_level, cv_summary, career_goals, months_in_training
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(employee_id) DO UPDATE SET
                role = excluded.role,
                department = excluded.department,
                experience_level = excluded.experience_level,
                known_skills = excluded.known_skills,
                learning_preferences = excluded.learning_preferences,
                access_level = excluded.access_level,
                cv_summary = excluded.cv_summary,
                career_goals = excluded.career_goals,
                months_in_training = excluded.months_in_training
            """,
            (
                profile.employee_id,
                profile.role,
                profile.department,
                profile.experience_level,
                json.dumps(profile.known_skills),
                json.dumps(profile.learning_preferences),
                profile.access_level,
                profile.cv_summary,
                json.dumps(profile.career_goals),
                profile.months_in_training,
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
        access_level=row["access_level"],
        cv_summary=row["cv_summary"],
        career_goals=json.loads(row["career_goals"]),
        months_in_training=int(row["months_in_training"]),
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


def save_course_progress(employee_id: str, course_id: str, status: str, progress_percent: int, saved_for_later: bool) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO course_progress (employee_id, course_id, status, progress_percent, saved_for_later)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(employee_id, course_id) DO UPDATE SET
                status = excluded.status,
                progress_percent = excluded.progress_percent,
                saved_for_later = excluded.saved_for_later
            """,
            (employee_id, course_id, status, progress_percent, int(saved_for_later)),
        )
        conn.commit()


def seed_course_progress(records: list[dict[str, object]]) -> None:
    with get_connection() as conn:
        for record in records:
            existing = conn.execute(
                """
                SELECT 1 FROM course_progress
                WHERE employee_id = ? AND course_id = ?
                """,
                (record["employee_id"], record["course_id"]),
            ).fetchone()
            if existing:
                continue
            conn.execute(
                """
                INSERT INTO course_progress (employee_id, course_id, status, progress_percent, saved_for_later)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record["employee_id"],
                    record["course_id"],
                    record["status"],
                    int(record["progress_percent"]),
                    int(bool(record["saved_for_later"])),
                ),
            )
        conn.commit()


def load_course_progress(employee_id: str) -> list[dict[str, int | str]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT employee_id, course_id, status, progress_percent, saved_for_later
            FROM course_progress
            WHERE employee_id = ?
            ORDER BY course_id
            """,
            (employee_id,),
        ).fetchall()
    return [
        {
            "employee_id": row["employee_id"],
            "course_id": row["course_id"],
            "status": row["status"],
            "progress_percent": row["progress_percent"],
            "saved_for_later": row["saved_for_later"],
        }
        for row in rows
    ]


def save_module_progress(employee_id: str, module_id: str, status: str, progress_percent: int, saved_for_later: bool) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO module_progress (employee_id, module_id, status, progress_percent, saved_for_later)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(employee_id, module_id) DO UPDATE SET
                status = excluded.status,
                progress_percent = excluded.progress_percent,
                saved_for_later = excluded.saved_for_later
            """,
            (employee_id, module_id, status, progress_percent, int(saved_for_later)),
        )
        conn.commit()


def load_module_progress(employee_id: str) -> list[dict[str, int | str]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT employee_id, module_id, status, progress_percent, saved_for_later
            FROM module_progress
            WHERE employee_id = ?
            ORDER BY module_id
            """,
            (employee_id,),
        ).fetchall()
    return [
        {
            "employee_id": row["employee_id"],
            "module_id": row["module_id"],
            "status": row["status"],
            "progress_percent": row["progress_percent"],
            "saved_for_later": row["saved_for_later"],
        }
        for row in rows
    ]


def load_all_course_progress() -> list[dict[str, int | str]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT employee_id, course_id, status, progress_percent, saved_for_later
            FROM course_progress
            ORDER BY employee_id, course_id
            """
        ).fetchall()
    return [
        {
            "employee_id": row["employee_id"],
            "course_id": row["course_id"],
            "status": row["status"],
            "progress_percent": row["progress_percent"],
            "saved_for_later": row["saved_for_later"],
        }
        for row in rows
    ]


def load_all_profiles() -> list[EmployeeProfile]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM profiles ORDER BY employee_id").fetchall()
    return [
        EmployeeProfile(
            employee_id=row["employee_id"],
            role=row["role"],
            department=row["department"],
            experience_level=row["experience_level"],
            known_skills=json.loads(row["known_skills"]),
            learning_preferences=json.loads(row["learning_preferences"]),
            access_level=row["access_level"],
            cv_summary=row["cv_summary"],
            career_goals=json.loads(row["career_goals"]),
            months_in_training=int(row["months_in_training"]),
        )
        for row in rows
    ]
