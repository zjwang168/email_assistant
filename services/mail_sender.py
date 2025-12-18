import os
import requests
from dotenv import load_dotenv
from typing import Optional, Dict, Any, List

load_dotenv(".env")

MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")


def _build_forward_text(forward_pkg: Dict[str, Any]) -> str:
    """
    Render a human-friendly forward template (NOT a robot summary).
    forward_pkg expected keys:
      - forward_subject: str
      - tone: "short" | "warm" | "formal"
      - key_points: list[str]
      - links: list[{label,url}]
      - has_calendar_event: bool (optional)
    """
    tone = (forward_pkg.get("tone") or "short").strip().lower()
    key_points: List[str] = forward_pkg.get("key_points") or []
    links: List[Dict[str, str]] = forward_pkg.get("links") or []

    bullets = "\n".join([f"- {str(p).strip()}" for p in key_points if str(p).strip()])
    if not bullets:
        bullets = "- (No key points extracted.)"

    primary_link = ""
    if links and isinstance(links, list) and isinstance(links[0], dict):
        primary_link = (links[0].get("url") or "").strip()

    # Mention calendar attachment (if present) in a natural way.
    has_cal = bool(forward_pkg.get("has_calendar_event", False))
    calendar_line = "I’ve attached a calendar invite (.ics) in case you want to add it quickly." if has_cal else ""

    if tone == "warm":
        parts = [
            "Hi everyone,",
            "",
            "I’m forwarding this in case it’s helpful. Here are the main points:",
            "",
            bullets,
        ]
        if primary_link:
            parts += ["", f"Official details: {primary_link}"]
        if calendar_line:
            parts += ["", calendar_line]
        parts += ["", "Looking forward to it 🙂", "Zijin"]
        return "\n".join([p for p in parts if p is not None]).strip()

    if tone == "formal":
        parts = [
            "Dear all,",
            "",
            "Please see the key details below:",
            "",
            bullets,
        ]
        if primary_link:
            parts += ["", f"Full details: {primary_link}"]
        if calendar_line:
            parts += ["", calendar_line]
        parts += ["", "Best regards,", "Zijin"]
        return "\n".join([p for p in parts if p is not None]).strip()

    # default short
    parts = [
        "Hi,",
        "",
        "Sharing the key details from the email:",
        "",
        bullets,
    ]
    if primary_link:
        parts += ["", f"Full details: {primary_link}"]
    if calendar_line:
        parts += ["", calendar_line]
    parts += ["", "Zijin"]
    return "\n".join([p for p in parts if p is not None]).strip()


def send_summary_email(
    to_email: str,
    subject: str,
    summary_data: Dict[str, Any],
    ics_path: Optional[str] = None,
) -> None:
    """
    Send a forward-template email back to the user via Mailgun.
    (Kept function name for compatibility with your main.py, but summary_data
    is now treated as forward_pkg.)

    If ics_path is provided, attach it as event.ics.
    """
    if not MAILGUN_API_KEY or not MAILGUN_DOMAIN:
        print("❌ Mailgun credentials missing")
        return

    forward_subject = (summary_data.get("forward_subject") or "").strip()
    mail_subject = forward_subject or (f"Fwd: {subject}" if subject else "Fwd: Email details")

    body_text = _build_forward_text(summary_data)

    data = {
        "from": f"Zijin Assistant <assistant@{MAILGUN_DOMAIN}>",
        "to": [to_email],
        "subject": mail_subject,
        "text": body_text,
    }

    files = None
    if ics_path:
        try:
            with open(ics_path, "rb") as f:
                files = [("attachment", ("event.ics", f.read(), "text/calendar"))]
        except FileNotFoundError:
            print(f"⚠️ ICS file not found at {ics_path}, sending without attachment.")
            files = None

    print(f"📤 Sending forward template to {to_email} via Mailgun...")
    resp = requests.post(
        f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
        auth=("api", MAILGUN_API_KEY),
        data=data,
        files=files,
    )
    print("Mailgun response:", resp.status_code, resp.text[:200])