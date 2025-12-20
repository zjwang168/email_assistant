# email_assistant/services/mail_sender.py
import os
import requests
from dotenv import load_dotenv

# Load .env for local dev; Render uses its Environment settings
load_dotenv(".env")
load_dotenv("../.env")

MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")


def _mailgun_ready() -> bool:
    return bool(MAILGUN_API_KEY and MAILGUN_DOMAIN)


def send_forward_email(
    to_email: str,
    forward_subject: str,
    forward_text: str,
    ics_content: str | None = None,
    attachments: list[tuple[str, bytes, str]] | None = None,
) -> None:
    """
    Send the FORWARD TEMPLATE email back to the user (your inbox).
    Optional: attach an .ics calendar invite if ics_content is provided.
    Optional: attach other files (e.g. images) via attachments list.
              Format: [(filename, content_bytes, content_type), ...]

    This function is the one main.py imports.
    """
    if not _mailgun_ready():
        print("❌ Mailgun credentials missing")
        return

    if not to_email:
        print("❌ Missing recipient email (sender)")
        return

    data = {
        "from": f"Zijin Assistant <assistant@{MAILGUN_DOMAIN}>",
        "to": [to_email],
        "subject": forward_subject or "Key Info",
        "text": forward_text or "",
    }

    files = []
    if ics_content:
        # Mailgun supports sending attachment bytes directly
        files.append(("attachment", ("event.ics", ics_content.encode("utf-8"), "text/calendar")))
    
    if attachments:
        for filename, content, ctype in attachments:
            files.append(("attachment", (filename, content, ctype)))
    
    if not files:
        files = None

    print(f"📤 Sending forward template to {to_email} via Mailgun...")
    resp = requests.post(
        f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
        auth=("api", MAILGUN_API_KEY),
        data=data,
        files=files,
        timeout=30,
    )
    print("Mailgun response:", resp.status_code, resp.text[:300])


# -----------------------------
# Backward-compatible function
# -----------------------------
def send_summary_email(
    to_email: str,
    subject: str,
    summary_data: dict,
    ics_content: str | None = None,
) -> None:
    """
    Backward compatibility: if older code calls send_summary_email.
    It will format summary_data into a text email, then send using Mailgun.
    Optional: attach an .ics calendar invite (ics_content).
    """
    lines: list[str] = []
    lines.append("💡 Here's what I found in your email:\n")

    summary = (summary_data.get("summary") or "").strip()
    if summary:
        lines.append("📋 Summary")
        lines.append(f"- {summary}\n")

    key_details = (summary_data.get("key_details") or "").strip()
    if key_details:
        lines.append("🕒 Key details")
        lines.append(f"- {key_details}\n")

    action_items = (summary_data.get("action_items") or "").strip()
    primary_link = summary_data.get("primary_link")
    if action_items or primary_link:
        lines.append("✅ Action")
        if action_items:
            lines.append(f"- {action_items}")
        if primary_link:
            lines.append(f"- Quick link: {primary_link}")
        lines.append("")

    calendar_note = (summary_data.get("calendar_note") or "").strip()
    if calendar_note:
        lines.append("📅 Calendar")
        lines.append(f"- {calendar_note}\n")

    lines.append("—")
    lines.append("🧭 Zijin Assistant")
    lines.append("Your AI-powered inbox helper")

    forward_text = "\n".join(lines)
    forward_subject = f"Summary: {subject}" if subject else "Email summary"

    send_forward_email(
        to_email=to_email,
        forward_subject=forward_subject,
        forward_text=forward_text,
        ics_content=ics_content,
    )