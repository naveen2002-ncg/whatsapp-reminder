from datetime import datetime, timedelta
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from db import get_reminders_after, init_db
from whatsapp import send_whatsapp

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


scheduler = BackgroundScheduler()
_started = False


def _parse_time_str(time_str: str) -> datetime:
    # HTML datetime-local sends: "YYYY-MM-DDTHH:MM"
    normalized = (time_str or "").strip().replace("T", " ")
    return datetime.strptime(normalized, "%Y-%m-%d %H:%M")


def start_scheduler() -> None:
    global _started
    if _started:
        logger.debug("[DIAGNOSTIC] Scheduler already started, skipping.")
        return
    scheduler.start()
    _started = True
    logger.info("[DIAGNOSTIC] APScheduler started successfully.")


def schedule_message(phone: str, message: str, time_str: str, reminder_id=None) -> None:
    logger.info(f"[DIAGNOSTIC] schedule_message called: phone={phone}, time_str={time_str}, reminder_id={reminder_id}")
    start_scheduler()

    try:
        run_time = _parse_time_str(time_str)
        logger.debug(f"[DIAGNOSTIC] Parsed run_time: {run_time}")
    except Exception as e:
        logger.error(f"[DIAGNOSTIC] Failed to parse time_str '{time_str}': {e}")
        raise

    # DB stores minute-level precision (HH:MM), so after a restart the same minute
    # can look slightly in the past because current time has seconds > 0.
    # Allow a small tolerance; APScheduler will run it as soon as possible.
    now = datetime.now()
    logger.debug(f"[DIAGNOSTIC] Current time: {now}, Run time: {run_time}")

    if run_time < (now - timedelta(minutes=1)):
        logger.warning(f"[DIAGNOSTIC] Rejected past time: run_time={run_time} is before {now - timedelta(minutes=1)}")
        raise ValueError("Reminder time must be in the future.")

    logger.info(
        f"[DIAGNOSTIC] Scheduling WhatsApp reminder (id={reminder_id}, run_time={run_time}, to={phone})"
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

    try:
        scheduler.add_job(send_whatsapp, **job_kwargs)
        logger.info(
            f"[DIAGNOSTIC] Scheduled job successfully (id={job_kwargs.get('id')}, run_date={job_kwargs.get('run_date')})"
        )
    except Exception as e:
        logger.error(f"[DIAGNOSTIC] Failed to schedule job: {e}")
        raise


def reschedule_pending() -> None:
    logger.info("[DIAGNOSTIC] reschedule_pending() called - reloading reminders from DB")
    # Re-load reminders from SQLite so scheduled jobs survive app restarts.
    start_scheduler()
    init_db()

    now_dt = datetime.now()
    logger.debug(f"[DIAGNOSTIC] Current time for filtering: {now_dt}")

    rows = get_reminders_after(now_dt=now_dt)
    logger.info(f"[DIAGNOSTIC] Found {len(rows)} pending reminders to reschedule")

    for reminder_id, _name, phone, message, time_str in rows:
        logger.debug(f"[DIAGNOSTIC] Rescheduling reminder_id={reminder_id}, phone={phone}, time={time_str}")
        try:
            schedule_message(phone, message, time_str, reminder_id=reminder_id)
        except Exception as e:
            logger.error(f"[DIAGNOSTIC] Failed to reschedule reminder_id={reminder_id}: {e}")

