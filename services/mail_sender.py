# services/mail_sender.py
import os
import requests
from dotenv import load_dotenv

load_dotenv(".env")


def send_summary_email(to_email, subject, summary, ics_content: str | None = None):
    MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
    MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")

    if not MAILGUN_API_KEY or not MAILGUN_DOMAIN:
        print("❌ Mailgun credentials missing")
        return

    print("DEBUG MAILGUN_DOMAIN =", MAILGUN_DOMAIN)
    print(f"📤 Sending summary email to {to_email} via Mailgun...")

    body_text = (
        "💡 Here's what I found in your email:\n\n"
        f"{summary}\n\n"
        "—\n"
        "🧭 Zijin Assistant\n"
        "Your AI-powered inbox helper"
    )

    data = {
        "from": f"Zijin Assistant <assistant@{MAILGUN_DOMAIN}>",
        "to": [to_email],
        "subject": f"Summary: {subject}",
        "text": body_text,
    }

    files = None
    if ics_content:
        files = [
            ("attachment", ("event.ics", ics_content, "text/calendar"))
        ]

    response = requests.post(
        f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
        auth=("api", MAILGUN_API_KEY),
        data=data,
        files=files,
    )

    print("Mailgun response:", response.status_code, response.text[:200])