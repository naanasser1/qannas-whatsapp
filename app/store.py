"""تخزين خفيف على SQLite: جلسة المحادثة لكل رقم + منع تكرار الرسائل."""

from __future__ import annotations

import sqlite3
import threading
import time

from . import config

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                wa_id      TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS seen_messages (
                message_id TEXT PRIMARY KEY,
                seen_at    REAL NOT NULL
            );
            """
        )
        _conn.commit()
    return _conn


def get_session(wa_id: str) -> str | None:
    """يرجع معرّف جلسة الأجينت المحفوظة لهذا الرقم، إن وُجدت."""
    with _lock:
        row = _connect().execute(
            "SELECT session_id FROM sessions WHERE wa_id = ?", (wa_id,)
        ).fetchone()
    return row[0] if row else None


def save_session(wa_id: str, session_id: str) -> None:
    with _lock:
        conn = _connect()
        conn.execute(
            "INSERT INTO sessions (wa_id, session_id, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(wa_id) DO UPDATE SET session_id = excluded.session_id, "
            "updated_at = excluded.updated_at",
            (wa_id, session_id, time.time()),
        )
        conn.commit()


def clear_session(wa_id: str) -> None:
    """يمسح ذاكرة المحادثة — يستدعيها أمر «جديد»."""
    with _lock:
        conn = _connect()
        conn.execute("DELETE FROM sessions WHERE wa_id = ?", (wa_id,))
        conn.commit()


def mark_seen(message_id: str) -> bool:
    """
    يسجّل معرّف الرسالة ويرجع True إذا كانت جديدة.

    Meta تعيد إرسال الويبهوك عند أي تأخر في الرد، وبدون هذا الفحص تنطلق
    نفس الدفعة مرتين وتُحرق التكلفة مرتين.
    """
    now = time.time()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "INSERT INTO seen_messages (message_id, seen_at) VALUES (?, ?)",
                (message_id, now),
            )
        except sqlite3.IntegrityError:
            return False
        # تنظيف السجلات الأقدم من ٧ أيام
        conn.execute("DELETE FROM seen_messages WHERE seen_at < ?", (now - 7 * 86400,))
        conn.commit()
    return True
