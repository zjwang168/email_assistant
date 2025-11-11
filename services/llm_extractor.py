# services/llm_extractor.py
import os
import json
import re
from dotenv import load_dotenv

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

load_dotenv(".env")


def _fallback_summary(subject: str, body: str) -> dict:
    """本地 / 出错时的简单兜底总结。"""
    clean_body = (body or "").strip().replace("\n", " ")
    snippet = clean_body[:280]

    return {
        "summary": snippet or "(Email body was empty.)",
        "key_details": f"Subject: {subject}" if subject else "",
        "action_items": "",
        "calendar_note": "",
        "primary_link": None,
    }


def summarize_email(subject: str, body: str) -> dict:
    """
    返回一个 dict:
    {
      "summary": str,         # 1–3 句话的极简总结
      "key_details": str,     # 可选，额外关键点（比如 subject）
      "action_items": str,    # 可选，需要做的事
      "calendar_note": str,   # 可选，和时间/地点相关的提示
      "primary_link": str|None  # 可选，RSVP/注册链接
    }
    """
    body = body or ""
    subject = subject or ""

    # 没有正文直接兜底
    if not body.strip():
        return _fallback_summary(subject, body)

    data: dict

    # ==== 先尝试用 OpenAI 总结 ====
    api_key = os.getenv("OPENAI_API_KEY")
    if OpenAI is not None and api_key:
        try:
            client = OpenAI(api_key=api_key)

            system_msg = (
                "You are a personal email assistant for a very busy grad student.\n"
                "Summarize emails in 1–3 short sentences, focused on what the user\n"
                "needs to know or do. If there is an obvious action (RSVP, register,\n"
                "pay, complete a form, choose a time), describe it very briefly.\n"
                "If there is ONE main event with a clear date/time/location, mention it\n"
                "in calendar_note (in plain English, not structured data).\n\n"
                "Respond ONLY as a JSON object with keys:\n"
                "  summary: string\n"
                "  key_details: string\n"
                "  action_items: string\n"
                "  calendar_note: string\n"
            )

            resp = client.responses.create(
                model="gpt-4.1-mini",
                input=[
                    {"role": "system", "content": system_msg},
                    {
                        "role": "user",
                        "content": f"Subject: {subject}\n\nBody:\n{body}",
                    },
                ],
                response_format={"type": "json_object"},
            )

            raw_text = resp.output[0].content[0].text
            data = json.loads(raw_text)
        except Exception as e:
            print("[LLM] Error, using fallback:", repr(e))
            data = _fallback_summary(subject, body)
    else:
        print("[LLM] No OPENAI_API_KEY or SDK, using fallback.")
        data = _fallback_summary(subject, body)

    # 保证这些 key 都存在并且是 string
    for key in ("summary", "key_details", "action_items", "calendar_note"):
        data[key] = str(data.get(key, "") or "").strip()

    # ==== 简单规则：如果需要 action，就抓正文里的第一个 URL 当作 quick link ====
    body_lower = body.lower()
    action_text = (data.get("action_items") or "").lower()

    needs_link = any(
        phrase in body_lower
        for phrase in [
            "rsvp",
            "register",
            "sign up",
            "signup",
            "sign-up",
            "complete the form",
            "fill out",
            "fill in",
            "submit",
            "payment",
            "pay by",
            "confirm your attendance",
        ]
    ) or any(
        phrase in action_text
        for phrase in [
            "rsvp",
            "register",
            "sign up",
            "signup",
            "sign-up",
            "fill out",
            "complete",
            "submit",
        ]
    )

    primary_link = None
    if needs_link:
        # 抓第一个 http(s) 链接
        match = re.search(r"https?://\S+", body)
        if match:
            primary_link = match.group(0)

    data["primary_link"] = primary_link

    return data