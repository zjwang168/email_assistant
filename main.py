# email_assistant/main.py
from fastapi import FastAPI, Request
from dotenv import load_dotenv
import tempfile

from email_assistant.services.mail_sender import send_summary_email
from email_assistant.services.llm_extractor import build_forward_package
from email_assistant.services.calendar_generator import (
    build_ics_from_calendar_event,
    detect_event_and_build_ics,
)

load_dotenv(".env")

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Email assistant is running!"}


@app.post("/email/webhook")
async def handle_incoming_email(request: Request):
    form_data = await request.form()

    sender = form_data.get("sender")
    subject = form_data.get("subject") or "(no subject)"
    body = form_data.get("body-plain") or ""

    print("\n📩 New email received")
    print("From:", sender)
    print("Subject:", subject)
    print("Body preview:", body[:200], "...")

    forward_pkg = build_forward_package(subject, body)

    # Build ICS:
    # 1) try LLM structured calendar_event
    ics_content = None
    if forward_pkg.get("has_calendar_event"):
        ics_content = build_ics_from_calendar_event(forward_pkg.get("calendar_event") or {})

    # 2) fallback heuristic detection from raw text
    if not ics_content:
        ics_content = detect_event_and_build_ics(subject, body)
        forward_pkg["has_calendar_event"] = bool(ics_content)

    ics_path = None
    if ics_content:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".ics", mode="w", encoding="utf-8")
        tmp.write(ics_content)
        tmp.close()
        ics_path = tmp.name
        print("📅 ICS generated at:", ics_path)

    send_summary_email(
        to_email=sender,
        subject=subject,
        summary_data=forward_pkg,
        ics_path=ics_path,
    )

    return {
        "status": "ok",
        "forward_subject": forward_pkg.get("forward_subject"),
        "has_calendar_event": forward_pkg.get("has_calendar_event"),
    }