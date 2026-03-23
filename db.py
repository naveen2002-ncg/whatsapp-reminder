import os
import sqlite3
from pathlib import Path


# Use /var/data for persistent storage on Render, local folder otherwise
if os.environ.get("RENDER"):
    DB_PATH = Path("/var/data/reminders.db")
    # Ensure the directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
else:
    DB_PATH = Path(__file__).resolve().parent / "reminders.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
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
