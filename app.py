import os
import re

from flask import Flask, render_template, request

from db import delete_reminder, init_db, insert_reminder
from scheduler import reschedule_pending, schedule_message, start_scheduler


app = Flask(__name__)


def _normalize_time_for_db(time_input: str) -> str:
    # HTML datetime-local sends "YYYY-MM-DDTHH:MM" but DB expects "YYYY-MM-DD HH:MM"
    return (time_input or "").strip().replace("T", " ")


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        message = (request.form.get("message") or "").strip()
        time_input = (request.form.get("time") or "").strip()

        if not name or not phone or not message or not time_input:
            return render_template("index.html", error="All fields are required.")

        # Validate phone digits early so we fail before scheduling.
        digits = re.sub(r"\D", "", phone)
        if len(digits) < 8:
            return render_template(
                "index.html",
                error="Phone number must include country code digits (example: 919876543210).",
            )

        time_str = _normalize_time_for_db(time_input)

        reminder_id = None
        try:
            reminder_id = insert_reminder(name, phone, message, time_str)
            schedule_message(phone, message, time_str, reminder_id=reminder_id)
            return render_template("index.html", success="Reminder scheduled.")
        except Exception as e:
            # If scheduling fails, keep DB clean.
            if reminder_id is not None:
                try:
                    delete_reminder(reminder_id)
                except Exception:
                    pass
            return render_template("index.html", error=str(e))

    return render_template("index.html")


def init_background_jobs_if_needed():
    """
    Flask debug mode runs the app twice (reloader).
    Only start APScheduler in the reloader child process.
    """

    # When running with the Flask reloader, WERKZEUG_RUN_MAIN is set to "true" in the child process.
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or os.environ.get("WERKZEUG_RUN_MAIN") is None:
        init_db()
        start_scheduler()
        reschedule_pending()


if __name__ == "__main__":
    init_background_jobs_if_needed()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)

