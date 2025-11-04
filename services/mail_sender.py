# services/mail_sender.py
import os
import requests
from dotenv import load_dotenv

# 确保这里也加载一下 .env（多次调用没关系）
load_dotenv(dotenv_path=".env")

def send_summary_email(to_email: str, original_subject: str, summary: str):
    """Send summarized reply email via Mailgun"""

    mailgun_domain = os.getenv("MAILGUN_DOMAIN")
    mailgun_api_key = os.getenv("MAILGUN_API_KEY")

    if not mailgun_domain or not mailgun_api_key:
        print("❌ Mailgun credentials missing in mail_sender.py")
        print("   MAILGUN_DOMAIN:", mailgun_domain)
        print("   MAILGUN_API_KEY:", mailgun_api_key)
        return

    print(f"📤 Sending summary email to {to_email} via Mailgun...")

    res = requests.post(
        f"https://api.mailgun.net/v3/{mailgun_domain}/messages",
        auth=("api", mailgun_api_key),
        data={
            "from": f"Assistant <assistant@{mailgun_domain}>",
            "to": [to_email],
            "subject": f"Re: {original_subject}",
            "text": summary,
        },
    )

    print("Mailgun response:", res.status_code, res.text[:200])
    return res