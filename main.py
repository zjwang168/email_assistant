# main.py
from fastapi import FastAPI, Request
from dotenv import load_dotenv
import os
from datetime import datetime

from services.mail_sender import send_summary_email
from services.llm_extractor import summarize_email
from services.calendar_generator import detect_event_and_build_ics

load_dotenv(".env")

print("Mailgun API KEY:", os.getenv("MAILGUN_API_KEY"))
print("Mailgun DOMAIN:", os.getenv("MAILGUN_DOMAIN"))

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

    print(f"\n📩 New email received from {sender}")
    print(f"Subject: {subject}")
    print(f"Body: {body[:200]}...")

    # 1) 生成摘要（LLM 或 fallback）
    summary = summarize_email(subject, body)

    # 2) 自动检测是否有事件，并生成 .ics 内容（可能是 None）
    ics_content = detect_event_and_build_ics(subject, body)

    # 3) 发送带 summary + 可选 .ics 的邮件
    send_summary_email(sender, subject, summary, ics_content)

    return {"status": "ok", "summary": summary}
