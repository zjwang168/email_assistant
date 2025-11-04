# main.py
from fastapi import FastAPI, Request
from dotenv import load_dotenv
import os
from datetime import datetime

from services.mail_sender import send_summary_email
from services.llm_extractor import summarize_email
from services.calendar_generator import generate_basic_ics  # ⭐ 新增

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

    # 1️⃣ 用 summarizer 生成摘要
    summary = summarize_email(subject, body)

    # 2️⃣ 先做一个 demo：如果 subject 里有 "Parent-teacher meeting"
    #    我们就假装这是一个 2025-11-06 15:00 的会，生成一个 .ics
    ics_content = None
    if "Parent-teacher" in subject or "Parent-teacher meeting" in subject:
        # 👉 这里先写死时间，MVP 测试用
        start_time = datetime(2025, 11, 6, 15, 0)
        ics_content = generate_basic_ics(
            summary="Parent-teacher meeting",
            description=summary,
            start_time=start_time,
            duration_minutes=60,
            location="Room 210",
        )

    # 3️⃣ 把 summary + (可选) ics 发回去
    send_summary_email(sender, subject, summary, ics_content=ics_content)

    return {"status": "ok", "summary": summary}