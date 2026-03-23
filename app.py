import os
import re
import logging

from flask import Flask, render_template, request, redirect, url_for, flash

from db import delete_reminder, get_all_reminders, get_dashboard_stats, init_db, insert_reminder
from scheduler import reschedule_pending, schedule_message, start_scheduler

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _validate_secret_key() -> str:
    """
    Validates and returns the Flask SECRET_KEY from environment.
    
    Raises:
        RuntimeError: If SECRET_KEY is not set or is insecure.
    """
    secret_key = os.environ.get("SECRET_KEY")
    
    if not secret_key:
        raise RuntimeError(
            "Missing SECRET_KEY environment variable. "
            "Please copy .env.example to .env and set a secure SECRET_KEY. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    
    # Warn if using a weak key in production
    if len(secret_key) < 32 and os.environ.get("FLASK_ENV") == "production":
        import warnings
        warnings.warn(
            "SECRET_KEY is shorter than 32 characters. "
            "Use a stronger key in production.",
            RuntimeWarning
        )
    
    return secret_key


app = Flask(__name__)
app.secret_key = _validate_secret_key()


def _normalize_time_for_db(time_input: str) -> str:
    return (time_input or "").strip().replace("T", " ")


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        logger.info("[DIAGNOSTIC] Form submission received")

        name = (request.form.get("name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        message = (request.form.get("message") or "").strip()
        time_input = (request.form.get("time") or "").strip()

        logger.debug(f"[DIAGNOSTIC] Form data: name={name}, phone={phone}, time_input={time_input}, message_len={len(message)}")

        if not name or not phone or not message or not time_input:
            logger.warning("[DIAGNOSTIC] Form validation failed: missing fields")
            flash("All fields are required.", "error")
            return render_template("index.html")

        digits = re.sub(r"\D", "", phone)
        if len(digits) < 8:
            logger.warning(f"[DIAGNOSTIC] Phone validation failed: {phone} (digits={len(digits)})")
            flash("Phone number must include country code digits (e.g. 919876543210).", "error")
            return render_template("index.html")

        time_str = _normalize_time_for_db(time_input)
        logger.info(f"[DIAGNOSTIC] Normalized time_str: {time_str}")

        reminder_id = None
        try:
            logger.info("[DIAGNOSTIC] Inserting reminder into database...")
            reminder_id = insert_reminder(name, phone, message, time_str)
            logger.info(f"[DIAGNOSTIC] Reminder inserted with id={reminder_id}")

            logger.info("[DIAGNOSTIC] Scheduling message...")
            schedule_message(phone, message, time_str, reminder_id=reminder_id)

            flash("Reminder scheduled successfully!", "success")
            logger.info("[DIAGNOSTIC] Reminder scheduled successfully!")
            return redirect(url_for("index"))
        except Exception as e:
            logger.error(f"[DIAGNOSTIC] Error during scheduling: {type(e).__name__}: {e}")
            if reminder_id is not None:
                try:
                    logger.info(f"[DIAGNOSTIC] Rolling back - deleting reminder_id={reminder_id}")
                    delete_reminder(reminder_id)
                except Exception as rollback_err:
                    logger.error(f"[DIAGNOSTIC] Rollback failed: {rollback_err}")
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


@app.route("/webhook/whatsapp", methods=["POST"])
def whatsapp_webhook():
    """
    Webhook endpoint to receive inbound WhatsApp messages from Twilio.
    When users reply to reminders, this endpoint:
    1. Logs the incoming message
    2. Finds pending reminders for that user
    3. Marks the most recent pending reminder as "acknowledged"
    4. Returns TwiML response to stop Twilio's default message
    """
    logger.info("[DIAGNOSTIC] Webhook called - inbound message received!")
    logger.debug(f"[DIAGNOSTIC] Request form data: {request.form}")
    
    # Extract message details from Twilio's webhook payload
    from_number = request.form.get("From", "unknown")
    body = request.form.get("Body", "").strip().lower()
    profile_name = request.form.get("ProfileName", "")
    
    logger.info(f"[DIAGNOSTIC] Inbound message: from={from_number}, profile={profile_name}, body='{body}'")
    
    # Normalize phone number (remove whatsapp: prefix and +)
    import re
    digits = re.sub(r"\D", "", from_number.replace("whatsapp:", ""))
    
    # Try to find and acknowledge pending reminders for this user
    acknowledged = False
    try:
        # Import here to avoid circular imports
        from db import get_all_reminders, update_reminder_status
        
        reminders = get_all_reminders()
        for reminder in reminders:
            reminder_phone_digits = re.sub(r"\D", "", reminder[2])  # phone is column index 2
            # Check if phone numbers match (last 10 digits)
            if digits[-10:] == reminder_phone_digits[-10:]:
                if reminder[4] in ('pending', 'sent'):  # status is column index 4
                    update_reminder_status(reminder[0], "acknowledged")
                    logger.info(f"[DIAGNOSTIC] Marked reminder_id={reminder[0]} as acknowledged for phone {digits[-10:]}")
                    acknowledged = True
                    break
    except Exception as e:
        logger.error(f"[DIAGNOSTIC] Error acknowledging reminder: {e}")
    
    if not acknowledged:
        logger.info(f"[DIAGNOSTIC] No pending reminders found for {digits[-10:]}")
    
    # Return empty TwiML response (acknowledges receipt without replying)
    twiml = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
    return Response(twiml, mimetype="application/xml")


@app.route("/webhook/test", methods=["GET", "POST"])
def webhook_test():
    """
    Test endpoint to verify webhook accessibility.
    """
    logger.info(f"[DIAGNOSTIC] Webhook test endpoint called with method: {request.method}")
    logger.debug(f"[DIAGNOSTIC] Request form data: {request.form}")
    return "Webhook test endpoint is reachable!", 200


def init_background_jobs_if_needed():
    logger.info("[DIAGNOSTIC] init_background_jobs_if_needed() called")
    werkzeug_main = os.environ.get("WERKZEUG_RUN_MAIN")
    logger.debug(f"[DIAGNOSTIC] WERKZEUG_RUN_MAIN={werkzeug_main}")

    if werkzeug_main == "true" or werkzeug_main is None:
        logger.info("[DIAGNOSTIC] Initializing database...")
        init_db()

        logger.info("[DIAGNOSTIC] Starting scheduler...")
        start_scheduler()

        logger.info("[DIAGNOSTIC] Rescheduling pending reminders...")
        reschedule_pending()
        logger.info("[DIAGNOSTIC] Background jobs initialized successfully")
    else:
        logger.debug("[DIAGNOSTIC] Skipping background jobs init (reloader process)")


if __name__ == "__main__":
    init_background_jobs_if_needed()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
