import os
import re
import logging
from pathlib import Path

from twilio.rest import Client
from dotenv import load_dotenv

from db import update_reminder_status

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
logger.debug(f"Loaded .env from: {Path(__file__).resolve().parent / '.env'}")


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


def _validate_twilio_config() -> tuple[str, str, str]:
    """
    Validates and returns Twilio configuration from environment variables.
    
    Raises:
        RuntimeError: If any required configuration is missing or invalid.
    
    Returns:
        Tuple of (account_sid, auth_token, from_whatsapp)
    """
    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_whatsapp = os.environ.get("TWILIO_WHATSAPP_FROM")
    
    missing = []
    if not account_sid:
        missing.append("TWILIO_ACCOUNT_SID")
    if not auth_token:
        missing.append("TWILIO_AUTH_TOKEN")
    if not from_whatsapp:
        missing.append("TWILIO_WHATSAPP_FROM")
    
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Please copy .env.example to .env and configure your Twilio credentials."
        )
    
    # Validate Account SID format
    if not account_sid.startswith("AC") or len(account_sid) != 34:
        raise RuntimeError(
            f"Invalid TWILIO_ACCOUNT_SID format. Expected 34 characters starting with 'AC', "
            f"got {len(account_sid)} characters."
        )
    
    # Validate Auth Token format (32 hex characters)
    if len(auth_token) != 32:
        raise RuntimeError(
            f"Invalid TWILIO_AUTH_TOKEN format. Expected 32 characters, "
            f"got {len(auth_token)}."
        )
    
    # Validate WhatsApp sender format
    if not from_whatsapp.startswith("whatsapp:+"):
        raise RuntimeError(
            f"Invalid TWILIO_WHATSAPP_FROM format. Expected 'whatsapp:+<number>', "
            f"got '{from_whatsapp}'."
        )
    
    return account_sid, auth_token, from_whatsapp


def send_whatsapp(phone: str, message: str, reminder_id=None) -> str:
    """
    Sends a WhatsApp message using Twilio.

    Updates reminder status to 'sent' on success or 'failed' on error.
    """
    logger.info(f"[DIAGNOSTIC] send_whatsapp called: phone={phone}, reminder_id={reminder_id}, message_len={len(message)}")

    # Load and validate configuration (no hardcoded defaults)
    account_sid, auth_token, from_whatsapp = _validate_twilio_config()

    logger.debug(
        f"[DIAGNOSTIC] Credentials loaded: "
        f"account_sid={'***' + account_sid[-4:] if account_sid else 'MISSING'}, "
        f"auth_token={'***' if auth_token else 'MISSING'}, "
        f"from={from_whatsapp}"
    )

    try:
        to_whatsapp = _format_whatsapp_to(phone)
        logger.info(f"[DIAGNOSTIC] Formatted phone: {to_whatsapp}")
    except Exception as e:
        logger.error(f"[DIAGNOSTIC] Phone formatting failed: {e}")
        raise

    client = Client(account_sid, auth_token)
    logger.info(f"[DIAGNOSTIC] Twilio client created, attempting to send message...")

    try:
        msg = client.messages.create(
            body=message,
            from_=from_whatsapp,
            to=to_whatsapp,
        )
        logger.info(f"[DIAGNOSTIC] WhatsApp sent SUCCESSFULLY: sid={msg.sid} to={to_whatsapp}")
        if reminder_id is not None:
            try:
                update_reminder_status(reminder_id, "sent")
                logger.info(f"[DIAGNOSTIC] Status updated to 'sent' for reminder_id={reminder_id}")
            except Exception as e:
                logger.error(f"[DIAGNOSTIC] Failed to update status for reminder id={reminder_id}: {e}")
        return msg.sid
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[DIAGNOSTIC] WhatsApp send FAILED to {to_whatsapp}: {type(e).__name__}: {error_msg}")
        
        # Check for common Twilio WhatsApp sandbox errors
        if "not a valid WhatsApp phone number" in error_msg.lower() or \
           "user is not opted in" in error_msg.lower() or \
           "63016" in error_msg or \
           "63018" in error_msg:
            logger.error(
                f"[DIAGNOSTIC] Twilio WhatsApp Sandbox Error: The number {to_whatsapp} has not opted in. "
                f"Recipient must send 'join <your-sandbox-code>' to +14155238886 before receiving messages."
            )
        
        if reminder_id is not None:
            try:
                update_reminder_status(reminder_id, "failed")
                logger.info(f"[DIAGNOSTIC] Status updated to 'failed' for reminder_id={reminder_id}")
            except Exception as ex:
                logger.error(f"[DIAGNOSTIC] Failed to update status for reminder id={reminder_id}: {ex}")
        raise
