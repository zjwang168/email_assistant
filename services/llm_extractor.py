# services/llm_extractor.py
import os
import json
import re
from typing import Optional

from dotenv import load_dotenv

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

load_dotenv(".env")


def _clean_email_body(body: str) -> str:
    """
    尽量去掉转发/回复里的 header，只保留真正正文内容。
    处理的东西大概包括：
    - '---------- Forwarded message ---------'
    - 'Original Message'
    - 以及以 From/To/Subject/Date: 开头的行
    """
    if not body:
        return ""

    lines = body.splitlines()
    cleaned_lines = []

    skipping_forward_header = False

    for line in lines:
        stripped = line.strip()

        # 常见转发分隔线
        if "Forwarded message" in stripped or "Original Message" in stripped:
            skipping_forward_header = True
            continue

        # 跳过 header 区块，直到遇到空行
        if skipping_forward_header:
            if stripped == "":
                skipping_forward_header = False
            continue

        # 典型 header 行（From/To/Subject/Date）
        if re.match(r"^(From|To|Cc|Subject|Date):", stripped):
            continue

        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines).strip()

    # 把连续很多空行压成最多 2 行
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 避免太长，截一部分就够 LLM 理解
    if len(text) > 8000:
        text = text[:8000] + "\n\n[truncated]"
    return text or body.strip()


def _fallback_summary(subject: str, body: str) -> dict:
    """本地 / 出错时的简单兜底总结（不用 OpenAI）。"""
    clean_body = _clean_email_body(body or "")
    single_line = clean_body.replace("\n", " ")
    snippet = single_line[:280]

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
      "summary": str,         # 1–3 句极简总结（重点）
      "key_details": str,     # 可选，额外关键点（比如 subject 或收件人范围）
      "action_items": str,    # 可选，需要做的事（RSVP / 注册 / 填表等）
      "calendar_note": str,   # 可选，和时间/地点相关的提示（自然语言）
      "primary_link": str|None  # 可选，RSVP/注册链接（如果有）
    }
    """
    subject = subject or ""
    raw_body = body or ""

    # 清洗后的正文，用来喂给 LLM & fallback
    cleaned_body = _clean_email_body(raw_body)

    if not cleaned_body.strip():
        return _fallback_summary(subject, raw_body)

    data: dict

    # ==== 先尝试用 OpenAI 总结 ====
    api_key = os.getenv("OPENAI_API_KEY")
    if OpenAI is not None and api_key:
        try:
            client: "OpenAI" = OpenAI(api_key=api_key)

            system_msg = (
                "You are a personal email assistant for a very busy grad student.\n"
                "Summarize emails in 1–3 very short sentences focused on what the user\n"
                "actually needs to know or do. Be concrete and high-signal.\n\n"
                "Guidelines:\n"
                "- Ignore greetings, signatures, and long lists of boilerplate.\n"
                "- If there are many related events, you can group them into one sentence.\n"
                "- If there is an obvious action (RSVP, register, pay, choose a time,\n"
                "  complete a form), describe it briefly in action_items.\n"
                "- If there is one main event/time/location, write a short note in\n"
                "  calendar_note in plain English (not structured data).\n\n"
                "Respond ONLY as a JSON object with keys:\n"
                "  summary: string  (1–3 short sentences, max ~260 chars)\n"
                "  key_details: string\n"
                "  action_items: string\n"
                "  calendar_note: string\n"
            )

            resp = client.responses.create(
                model="gpt-5-mini",
                input=[
                    {"role": "system", "content": system_msg},
                    {
                        "role": "user",
                        "content": f"Subject: {subject}\n\nBody:\n{cleaned_body}",
                    },
                ],
                response_format={"type": "json_object"},
            )

            # 兼容 openai>=2.0 的 Responses 返回格式
            content_block = resp.output[0].content[0].text
            raw_text = getattr(content_block, "value", content_block)
            data = json.loads(raw_text)
        except Exception as e:
            print("[LLM] Error, using fallback:", repr(e))
            data = _fallback_summary(subject, raw_body)
    else:
        print("[LLM] No OPENAI_API_KEY or SDK, using fallback.")
        data = _fallback_summary(subject, raw_body)

    # 保证这些 key 都存在并且是 string
    for key in ("summary", "key_details", "action_items", "calendar_note"):
        data[key] = str(data.get(key, "") or "").strip()

    # ==== 简单规则：如果需要 action，就抓正文里的第一个 URL 当作 quick link ====
    body_lower = cleaned_body.lower()
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
        match = re.search(r"https?://\S+", raw_body)
        if match:
            primary_link = match.group(0)

    data["primary_link"] = primary_link

    return data