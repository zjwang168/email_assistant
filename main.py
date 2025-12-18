import os
from fastapi import FastAPI, Request
from dotenv import load_dotenv

from services.mail_sender import send_forward_email  # 你现在用的是转发模板逻辑
from services.llm_extractor import build_forward_package
from services.calendar_generator import detect_event_and_build_ics

load_dotenv(".env")  # 本地用；Render 上用 Environment Variables

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

    sender = form_data.get("sender")
    subject = form_data.get("subject") or "(no subject)"
    body = form_data.get("body-plain") or ""

    print("\n📩 New email received")
    print(f"From: {sender}")
    print(f"Subject: {subject}")
    print(f"Body preview: {body[:200]}...")

    # 1) 生成转发模板内容（LLM 或 fallback）
    forward_pkg = build_forward_package(subject, body)

    # 2) 检测是否有日历事件（生成 .ics 内容 or None）
    ics_content = detect_event_and_build_ics(subject, body)

    # 3) 发送转发模板（带可选 .ics）
    send_forward_email(
        to_email=sender,
        forward_subject=forward_pkg["forward_subject"],
        forward_text=forward_pkg["forward_text"],
        ics_content=ics_content,
    )

    return {
        "status": "ok",
        "forward_subject": forward_pkg["forward_subject"],
        "has_calendar_event": bool(ics_content),
    }