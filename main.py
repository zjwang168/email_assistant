# email_assistant/main.py
import os
import tempfile
from fastapi import FastAPI, Request
from dotenv import load_dotenv

from services.llm_extractor import build_forward_package
from services.calendar_generator import detect_event_and_build_ics, build_ics_from_calendar_event
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
    # Filter out image artifacts before processing
    cleaned_body = body.replace("[image: ]", "").replace("[image:]", "")
    forward_pkg = build_forward_package(subject, cleaned_body)
    forward_subject = forward_pkg.get("forward_subject") or f"{subject} – Key Info"

    # Construct forward_text from key_points and links
    key_points = forward_pkg.get("key_points") or []
    links = forward_pkg.get("links") or []

    summary_lines = []
    if key_points:
        summary_lines.append("Key Points:")
        for kp in key_points:
            summary_lines.append(f"- {kp}")
    else:
        summary_lines.append("(No key points generated.)")

    if links:
        summary_lines.append("\nLinks:")
        for link in links:
            label = link.get("label", "Link")
            url = link.get("url", "")
            summary_lines.append(f"- {label}: {url}")

    forward_text = "\n".join(summary_lines)

    # 2) Detect calendar event and generate ICS content (string or None)
    # Priority: LLM detection > Heuristic detection
    ics_content = None
    if forward_pkg.get("has_calendar_event") and forward_pkg.get("calendar_event"):
        ics_content = build_ics_from_calendar_event(forward_pkg["calendar_event"])

    if not ics_content:
        # Fallback to heuristic
        ics_content = detect_event_and_build_ics(subject, body)

    # 2.5) Handle Attachments
    # Mailgun sends attachments as "attachment-x" in form_data, and we can access files via request.form() upload objects?
    # Actually, Starlette/FastAPI handles multipart uploads via request.form() where values can be UploadFile.
    # But Mailgun webhooks might send them differently. Let's inspect form_data keys.
    # Typically: "attachment-1", "attachment-2", etc. or just "attachment" list.
    
    # We will collect attachments to forward.
    forward_attachments = []
    
    # Iterate over all form fields to find UploadFile objects
    for key, value in form_data.items():
        # In Starlette, uploaded files appear as Starlette.datastructures.UploadFile
        # But here value might be a string if it's a text field.
        # We check if it has a 'filename' attribute or similar, or check type.
        if hasattr(value, "filename") and value.filename:
            # It's a file!
            content = await value.read()
            forward_attachments.append((value.filename, content, value.content_type or "application/octet-stream"))
            print(f"📎 Found attachment: {value.filename} ({len(content)} bytes)")

    # 3) Send forward template email (with optional .ics attachment)
    send_forward_email(
        to_email=sender,
        forward_subject=forward_subject,
        forward_text=forward_text,
        ics_content=ics_content,
        attachments=forward_attachments,
    )

    return {
        "status": "ok",
        "forward_subject": forward_subject,
        "has_calendar_event": bool(ics_content),
    }