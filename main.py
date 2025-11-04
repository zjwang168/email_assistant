from fastapi import FastAPI, Request
from dotenv import load_dotenv
import os
from services.mail_sender import send_summary_email

# 1️⃣ 加载环境变量
load_dotenv(dotenv_path=".env")

MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")

print(f"Mailgun API KEY: {MAILGUN_API_KEY}")
print(f"Mailgun DOMAIN: {MAILGUN_DOMAIN}")

# 2️⃣ 初始化 FastAPI
app = FastAPI(title="Email Assistant API", version="0.1")

# 3️⃣ 健康检查路由
@app.get("/")
async def root():
    return {"message": "Email assistant is running!"}

# 4️⃣ Webhook 路由
@app.post("/email/webhook")
async def handle_incoming_email(request: Request):
    """Receive email data from Mailgun webhook"""
    try:
        form_data = await request.form()
        sender = form_data.get("sender")
        subject = form_data.get("subject")
        body = form_data.get("body-plain", "")

        print(f"\n📩 New email received from {sender}")
        print(f"Subject: {subject}")
        print(f"Body: {body[:200]}...")  # 打印前200字符，防止太长

        # Step 1️⃣：生成简单摘要（mock）
        summary = f"Summary of '{subject}': {body[:100]}..."

        # Step 2️⃣：发送回信
        send_summary_email(sender, subject, summary)

        return {"status": "ok", "summary": summary}

    except Exception as e:
        print("❌ Error handling webhook:", e)
        return {"status": "error", "detail": str(e)}