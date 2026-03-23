import os
import re

from flask import Flask, render_template, request, redirect, url_for, flash

from db import delete_reminder, get_all_reminders, get_dashboard_stats, init_db, insert_reminder
from scheduler import reschedule_pending, schedule_message, start_scheduler


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "whatsapp-reminder-dev-key")


def _normalize_time_for_db(time_input: str) -> str:
    return (time_input or "").strip().replace("T", " ")


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        message = (request.form.get("message") or "").strip()
        time_input = (request.form.get("time") or "").strip()

        if not name or not phone or not message or not time_input:
            flash("All fields are required.", "error")
            return render_template("index.html")

        digits = re.sub(r"\D", "", phone)
        if len(digits) < 8:
            flash("Phone number must include country code digits (e.g. 919876543210).", "error")
            return render_template("index.html")

        time_str = _normalize_time_for_db(time_input)

        reminder_id = None
        try:
            reminder_id = insert_reminder(name, phone, message, time_str)
            schedule_message(phone, message, time_str, reminder_id=reminder_id)
            flash("Reminder scheduled successfully!", "success")
            return redirect(url_for("index"))
        except Exception as e:
            if reminder_id is not None:
                try:
                    delete_reminder(reminder_id)
                except Exception:
                    pass
            flash(str(e), "error")
            return render_template("index.html")

    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    reminders = get_all_reminders()
    stats = get_dashboard_stats()
    return render_template("dashboard.html", reminders=reminders, stats=stats)


@app.route("/reminders/<int:reminder_id>/delete", methods=["POST"])
def remove_reminder(reminder_id):
    try:
        delete_reminder(reminder_id)
        flash("Reminder deleted.", "success")
    except Exception as e:
        flash(f"Failed to delete: {e}", "error")
    return redirect(url_for("dashboard"))


def init_background_jobs_if_needed():
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or os.environ.get("WERKZEUG_RUN_MAIN") is None:
        init_db()
        start_scheduler()
        reschedule_pending()


if __name__ == "__main__":
    init_background_jobs_if_needed()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
