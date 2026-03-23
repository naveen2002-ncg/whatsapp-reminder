import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "reminders.db"


def get_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


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
            time TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def insert_reminder(name: str, phone: str, message: str, time_str: str) -> int:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO reminders (name, phone, message, time) VALUES (?, ?, ?, ?)",
        (name, phone, message, time_str),
    )
    conn.commit()
    reminder_id = cursor.lastrowid
    conn.close()
    return int(reminder_id)


def get_reminders_after(now_dt=None):
    conn = get_conn()
    cursor = conn.cursor()

    if now_dt is not None:
        now_str = now_dt.strftime("%Y-%m-%d %H:%M")
        cursor.execute(
            "SELECT id, name, phone, message, time FROM reminders WHERE time >= ? ORDER BY time ASC",
            (now_str,),
        )
    else:
        cursor.execute("SELECT id, name, phone, message, time FROM reminders ORDER BY time ASC")

    rows = cursor.fetchall()
    conn.close()
    return rows


def delete_reminder(reminder_id: int) -> None:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()

