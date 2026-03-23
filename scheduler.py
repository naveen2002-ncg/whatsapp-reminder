from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from db import get_reminders_after, init_db
from whatsapp import send_whatsapp


scheduler = BackgroundScheduler()
_started = False


def _parse_time_str(time_str: str) -> datetime:
    # HTML datetime-local sends: "YYYY-MM-DDTHH:MM"
    normalized = (time_str or "").strip().replace("T", " ")
    return datetime.strptime(normalized, "%Y-%m-%d %H:%M")


def start_scheduler() -> None:
    global _started
    if _started:
        return
    scheduler.start()
    _started = True
    print("APScheduler started.")


def schedule_message(phone: str, message: str, time_str: str, reminder_id=None) -> None:
    start_scheduler()

    run_time = _parse_time_str(time_str)
    # DB stores minute-level precision (HH:MM), so after a restart the same minute
    # can look slightly in the past because current time has seconds > 0.
    # Allow a small tolerance; APScheduler will run it as soon as possible.
    now = datetime.now()
    if run_time < (now - timedelta(minutes=1)):
        raise ValueError("Reminder time must be in the future.")

    print(
        "Scheduling WhatsApp reminder"
        f"(id={reminder_id}, run_time={run_time}, to={phone})."
    )

    job_kwargs = dict(
        trigger="date",
        run_date=run_time,
        args=[phone, message],
        kwargs={"reminder_id": reminder_id},
        misfire_grace_time=60 * 60,  # 1 hour
    )

    if reminder_id is not None:
        job_kwargs["id"] = f"reminder_{reminder_id}"
        job_kwargs["replace_existing"] = True

    scheduler.add_job(send_whatsapp, **job_kwargs)
    print(
        "Scheduled job successfully"
        f"(id={job_kwargs.get('id')}, run_date={job_kwargs.get('run_date')})."
    )


def reschedule_pending() -> None:
    # Re-load reminders from SQLite so scheduled jobs survive app restarts.
    start_scheduler()
    init_db()

    now_dt = datetime.now()
    rows = get_reminders_after(now_dt=now_dt)
    print(f"Rescheduling pending reminders: {len(rows)} found.")
    for reminder_id, _name, phone, message, time_str in rows:
        schedule_message(phone, message, time_str, reminder_id=reminder_id)

