import os
import re
from pathlib import Path

from twilio.rest import Client
from dotenv import load_dotenv

from db import update_reminder_status

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")


def _normalize_phone_digits(phone: str) -> str:
    digits = re.sub(r"\D", "", str(phone or ""))
    if len(digits) < 8:
        raise ValueError(
            "Phone number must include country code digits (example: 919876543210)."
        )
    return digits


def _format_whatsapp_to(phone: str) -> str:
    digits = _normalize_phone_digits(phone)
    return f"whatsapp:+{digits}"


def send_whatsapp(phone: str, message: str, reminder_id=None) -> str:
    """
    Sends a WhatsApp message using Twilio.

    Updates reminder status to 'sent' on success or 'failed' on error.
    """

    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_whatsapp = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

    if not account_sid or not auth_token:
        raise RuntimeError(
            "Missing Twilio credentials. Create a `.env` file or set TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN."
        )

    to_whatsapp = _format_whatsapp_to(phone)

    client = Client(account_sid, auth_token)
    try:
        msg = client.messages.create(
            body=message,
            from_=from_whatsapp,
            to=to_whatsapp,
        )
        print(f"WhatsApp sent: sid={msg.sid} to={to_whatsapp}")
        if reminder_id is not None:
            try:
                update_reminder_status(reminder_id, "sent")
            except Exception as e:
                print(f"Failed to update status for reminder id={reminder_id}: {e}")
        return msg.sid
    except Exception as e:
        print(f"WhatsApp send failed to {to_whatsapp}: {e}")
        if reminder_id is not None:
            try:
                update_reminder_status(reminder_id, "failed")
            except Exception as ex:
                print(f"Failed to update status for reminder id={reminder_id}: {ex}")
        raise
