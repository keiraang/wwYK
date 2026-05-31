"""
database.py — SQLite setup and helper queries for wwYK.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "wwyk.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                name    TEXT NOT NULL UNIQUE,
                xp      INTEGER NOT NULL DEFAULT 0,
                points  INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS skills (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id),
                name        TEXT NOT NULL,
                description TEXT,
                xp_awarded  INTEGER NOT NULL DEFAULT 0,
                added_at    TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS challenges (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                challenger_id   INTEGER NOT NULL REFERENCES users(id),
                opponent_id     INTEGER NOT NULL REFERENCES users(id),
                skill_name      TEXT NOT NULL,
                challenge_type  TEXT NOT NULL,   -- challenger_knows | opponent_knows | neither_knows
                format          TEXT,            -- quiz | oral | written | etc.
                stakes_desc     TEXT,            -- chore, points, bragging rights, etc.
                stakes_points   INTEGER NOT NULL DEFAULT 0,
                status          TEXT NOT NULL DEFAULT 'pending',  -- pending | active | completed | scheduled
                scheduled_at    TEXT,
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                result          TEXT             -- JSON blob set on completion
            );

            CREATE TABLE IF NOT EXISTS xp_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL REFERENCES users(id),
                delta        INTEGER NOT NULL,
                reason       TEXT NOT NULL,
                created_at   TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS points_log (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL REFERENCES users(id),
                delta        INTEGER NOT NULL,
                reason       TEXT NOT NULL,
                created_at   TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        # Seed default family members if the table is empty
        existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if existing == 0:
            names = ["Garrett", "Keira", "Leo", "Papa", "Mama", "Kuya", "William"]
            seed_xp = [180, 160, 120, 99, 75, 32, 31]
            for name, xp in zip(names, seed_xp):
                conn.execute(
                    "INSERT INTO users (name, xp, points) VALUES (?, ?, ?)",
                    (name, xp, 0),
                )
        conn.commit()


# ---------------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------------

def get_all_users():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users ORDER BY xp DESC").fetchall()


def get_user(user_id: int):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def get_user_by_name(name: str):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchone()


def apply_xp(user_id: int, delta: int, reason: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET xp = MAX(0, xp + ?) WHERE id = ?", (delta, user_id))
        conn.execute(
            "INSERT INTO xp_log (user_id, delta, reason) VALUES (?, ?, ?)",
            (user_id, delta, reason),
        )
        conn.commit()


def apply_points(user_id: int, delta: int, reason: str):
    with get_conn() as conn:
        conn.execute("UPDATE users SET points = points + ? WHERE id = ?", (delta, user_id))
        conn.execute(
            "INSERT INTO points_log (user_id, delta, reason) VALUES (?, ?, ?)",
            (user_id, delta, reason),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Skill helpers
# ---------------------------------------------------------------------------

def get_skills(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM skills WHERE user_id = ? ORDER BY added_at DESC", (user_id,)
        ).fetchall()


def add_skill(user_id: int, name: str, description: str, xp_awarded: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO skills (user_id, name, description, xp_awarded) VALUES (?, ?, ?, ?)",
            (user_id, name, description, xp_awarded),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Challenge helpers
# ---------------------------------------------------------------------------

def create_challenge(
    challenger_id, opponent_id, skill_name, challenge_type,
    format_, stakes_desc, stakes_points, scheduled_at=None
):
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO challenges
               (challenger_id, opponent_id, skill_name, challenge_type,
                format, stakes_desc, stakes_points, status, scheduled_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                challenger_id, opponent_id, skill_name, challenge_type,
                format_, stakes_desc, stakes_points,
                "scheduled" if scheduled_at else "active",
                scheduled_at,
            ),
        )
        conn.commit()
        return cur.lastrowid


def get_challenge(challenge_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM challenges WHERE id = ?", (challenge_id,)
        ).fetchone()


def get_challenges_for_user(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            """SELECT c.*,
                      u1.name AS challenger_name,
                      u2.name AS opponent_name
               FROM challenges c
               JOIN users u1 ON c.challenger_id = u1.id
               JOIN users u2 ON c.opponent_id   = u2.id
               WHERE c.challenger_id = ? OR c.opponent_id = ?
               ORDER BY c.created_at DESC""",
            (user_id, user_id),
        ).fetchall()


def complete_challenge(challenge_id: int, result_json: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE challenges SET status = 'completed', result = ? WHERE id = ?",
            (result_json, challenge_id),
        )
        conn.commit()


def get_xp_log(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM xp_log WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
            (user_id,),
        ).fetchall()


def get_points_log(user_id: int):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM points_log WHERE user_id = ? ORDER BY created_at DESC LIMIT 20",
            (user_id,),
        ).fetchall()
