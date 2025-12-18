# email_assistant/main.py
import os
import tempfile
from fastapi import FastAPI, Request
from dotenv import load_dotenv

from services.llm_extractor import build_forward_package
from services.calendar_generator import detect_event_and_build_ics
from services.mail_sender import send_forward_email


# Load .env for local dev ONLY; Render uses Dashboard env vars
# Try both "email_assistant/.env" and repo root ".env" safely
load_dotenv(".env")
load_dotenv("../.env")

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Email assistant is running!"}


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/email/webhook")
async def handle_incoming_email(request: Request):
    form_data = await request.form()

    sender = form_data.get("sender") or ""
    subject = form_data.get("subject") or "(no subject)"
    body = form_data.get("body-plain") or ""

    print("\n📩 New email received")
    print(f"From: {sender}")
    print(f"Subject: {subject}")
    print(f"Body preview: {body[:200]}...")

    # 1) Build forward template package (subject + formatted text)
    forward_pkg = build_forward_package(subject, body)
    forward_subject = forward_pkg.get("forward_subject") or f"{subject} – Key Info"
    forward_text = forward_pkg.get("forward_text") or "(No summary generated.)"

    # 2) Detect calendar event and generate ICS content (string or None)
    ics_content = detect_event_and_build_ics(subject, body)

    # 3) Send forward template email (with optional .ics attachment)
    send_forward_email(
        to_email=sender,
        forward_subject=forward_subject,
        forward_text=forward_text,
        ics_content=ics_content,
    )

    return {
        "status": "ok",
        "forward_subject": forward_subject,
        "has_calendar_event": bool(ics_content),
    }