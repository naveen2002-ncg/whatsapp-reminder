# WhatsApp Reminder (Flask + Twilio + APScheduler)

A simple “schedule a WhatsApp message” app:

1. User enters: name, phone, reminder date/time, message
2. System stores it in SQLite
3. APScheduler sends the message at the scheduled time using Twilio WhatsApp API

## Project Files

- `app.py` - Main Flask app (routes + logic)
- `scheduler.py` - Scheduling logic (APScheduler)
- `whatsapp.py` - Twilio message sending
- `db.py` - Database setup & functions
- `templates/index.html` - Input form UI
- `static/style.css` - Basic styling
- `requirements.txt` - Dependencies

## Step 1 — Setup Twilio WhatsApp (Sandbox)

1. Create a Twilio account
2. Activate WhatsApp Sandbox
3. Get:
   - `Account SID`
   - `Auth Token`
   - Sandbox “from” number (commonly `whatsapp:+14155238886`)

### Twilio credentials (set env vars)

You have two options:

1) Use a `.env` file (recommended)
2) Set Windows environment variables in PowerShell

### Option A — Use `.env` file (recommended)

1. Copy `.env.example` to `.env`
2. Fill in your:
   - `TWILIO_ACCOUNT_SID`
   - `TWILIO_AUTH_TOKEN`
   - `TWILIO_WHATSAPP_FROM` (optional)

### Option B — Set environment variables in PowerShell

Set these environment variables before running the app:

- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_WHATSAPP_FROM` (optional; defaults to `whatsapp:+14155238886`)

Example in PowerShell:

```powershell
$env:TWILIO_ACCOUNT_SID="YOUR_ACCOUNT_SID"
$env:TWILIO_AUTH_TOKEN="YOUR_AUTH_TOKEN"
$env:TWILIO_WHATSAPP_FROM="whatsapp:+14155238886"
```

### Test sending a message (Twilio sandbox)

Run this script first to confirm your credentials work:

```python
from twilio.rest import Client

client = Client("ACCOUNT_SID", "AUTH_TOKEN")

message = client.messages.create(
    body="Test message",
    from_="whatsapp:+14155238886",
    to="whatsapp:+91XXXXXXXXXX",
)

print(message.sid)
```

If this works, you’re good to proceed to the Flask scheduler tests.

## Step 2 — Run locally (Day 1 + Day 2)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Then open:

`http://127.0.0.1:5000/`

## Step 3 — How phone numbers work (important)

In the form, enter the phone number as **digits including country code**, without `+`.

Examples:

- India: `919876543210`
- US: `14155550123`

The app converts it to `whatsapp:+<digits>` for Twilio.

## Step 4 — Manual testing (don’t skip)

Make sure you can send messages in the Twilio sandbox first (use the Twilio snippet from your instructions).

Then test these cases:

1. Message after 1 minute
2. Message after 5 minutes
3. Wrong number handling

Wrong number handling expectations:
- If Twilio rejects the number or sandbox rules block it, the scheduled job will fail safely and your Flask app won’t crash.
- You’ll see the error in the terminal where `python app.py` is running.

## Step 5 — Deploy (Day 3)

Recommended: Render or Railway (single worker).

General steps:
1. Push to GitHub
2. Connect to Render/Railway
3. Deploy Flask app
4. Set the same env vars (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`)

Scheduler note:
- APScheduler runs in-process. For production, deploy as a single instance to avoid duplicate sends.

