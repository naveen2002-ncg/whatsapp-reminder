import os
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Use appropriate path for database based on environment
# On Render: use /tmp for ephemeral storage (data lost on sleep)
# On local: use local folder
if os.environ.get("RENDER"):
    # Render free tier: use /tmp (ephemeral, data lost after sleep)
    # For persistence, upgrade to Render Disk or use external DB
    DB_PATH = Path("/tmp/reminders.db")
    logger.info(f"[DIAGNOSTIC] Running on Render, using DB_PATH={DB_PATH}")
else:
    DB_PATH = Path(__file__).resolve().parent / "reminders.db"
    logger.info(f"[DIAGNOSTIC] Running locally, using DB_PATH={DB_PATH}")

# Ensure database directory exists
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    try:
        logger.info(f"[DIAGNOSTIC] init_db() called, DB_PATH={DB_PATH}")
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY,
                name TEXT,
                phone TEXT,
                message TEXT,
                time TEXT,
                status TEXT DEFAULT 'pending'
            )
            """
        )
        # Migrate: add status column if table existed before this change.
        try:
            cursor.execute("ALTER TABLE reminders ADD COLUMN status TEXT DEFAULT 'pending'")
        except sqlite3.OperationalError:
            pass  # Column already exists.
        conn.commit()
        conn.close()
        logger.info("[DIAGNOSTIC] init_db() completed successfully")
    except Exception as e:
        logger.error(f"[DIAGNOSTIC] init_db() FAILED: {e}")
        raise


def insert_reminder(name: str, phone: str, message: str, time_str: str) -> int:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO reminders (name, phone, message, time, status) VALUES (?, ?, ?, ?, 'pending')",
        (name, phone, message, time_str),
    )
    conn.commit()
    reminder_id = cursor.lastrowid
    conn.close()
    return int(reminder_id)


def get_all_reminders():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, phone, message, time, status FROM reminders ORDER BY time DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_reminders_after(now_dt=None):
    conn = get_conn()
    cursor = conn.cursor()

    if now_dt is not None:
        now_str = now_dt.strftime("%Y-%m-%d %H:%M")
        cursor.execute(
            "SELECT id, name, phone, message, time FROM reminders WHERE time >= ? AND status = 'pending' ORDER BY time ASC",
            (now_str,),
        )
    else:
        cursor.execute("SELECT id, name, phone, message, time FROM reminders WHERE status = 'pending' ORDER BY time ASC")

    rows = cursor.fetchall()
    conn.close()
    return rows


def update_reminder_status(reminder_id: int, status: str) -> None:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("UPDATE reminders SET status = ? WHERE id = ?", (status, reminder_id))
    conn.commit()
    conn.close()


def delete_reminder(reminder_id: int) -> None:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()


def get_dashboard_stats():
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM reminders")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM reminders WHERE status = 'pending'")
    pending = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM reminders WHERE status = 'sent'")
    sent = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM reminders WHERE status = 'failed'")
    failed = cursor.fetchone()[0]
    conn.close()
    return {"total": total, "pending": pending, "sent": sent, "failed": failed}
