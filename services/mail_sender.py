# services/mail_sender.py
import os
import requests
from dotenv import load_dotenv

load_dotenv(".env")

MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")


def _build_email_text(subject: str, summary_data: dict) -> str:
    """把 summary_data 格式化成一封简洁的文本邮件。"""

    lines: list[str] = []
    lines.append("💡 Here's what I found in your email:\n")

    # 1) Summary（一定要有）
    summary = (summary_data.get("summary") or "").strip()
    if summary:
        lines.append("📋 Summary")
        lines.append(f"- {summary}\n")

    # 2) Key details（可有可无）
    key_details = (summary_data.get("key_details") or "").strip()
    if key_details:
        lines.append("🕒 Key details")
        lines.append(f"- {key_details}\n")

    # 3) Action + Quick link（只有真的有事要做时才出现）
    action_items = (summary_data.get("action_items") or "").strip()
    primary_link = summary_data.get("primary_link")

    if action_items or primary_link:
        lines.append("✅ Action")
        if action_items:
            lines.append(f"- {action_items}")
        if primary_link:
            lines.append(f"- Quick link: {primary_link}")
        lines.append("")  # 空行分隔

    # 4) Calendar 文本（以后可以配合 .ics 更智能）
    calendar_note = (summary_data.get("calendar_note") or "").strip()
    if calendar_note:
        lines.append("📅 Calendar")
        lines.append(f"- {calendar_note}\n")

    # 结尾签名
    lines.append("—")
    lines.append("🧭 Zijin Assistant")
    lines.append("Your AI-powered inbox helper")

    return "\n".join(lines)


def send_summary_email(
    to_email: str,
    subject: str,
    summary_data: dict,
    ics_path: str | None = None,
) -> None:
    """通过 Mailgun 把总结发回给用户（可选带 .ics 附件）。"""

    if not MAILGUN_API_KEY or not MAILGUN_DOMAIN:
        print("❌ Mailgun credentials missing")
        return

    body_text = _build_email_text(subject, summary_data)

    data = {
        "from": f"Zijin Assistant <assistant@{MAILGUN_DOMAIN}>",
        "to": [to_email],
        "subject": f"Summary: {subject}" if subject else "Email summary",
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

    print(f"📤 Sending summary email to {to_email} via Mailgun...")
    resp = requests.post(
        f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
        auth=("api", MAILGUN_API_KEY),
        data=data,
        files=files,
    )
    print("Mailgun response:", resp.status_code, resp.text[:200])