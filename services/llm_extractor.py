# services/llm_extractor.py
import os
from dotenv import load_dotenv

load_dotenv(".env")

try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # openai SDK 有问题时直接走 fallback


ASSISTANT_STYLE = os.getenv("ASSISTANT_STYLE", "structured").lower()
# 可选:
# - "structured" -> emoji + 分区标题
# - "minimal"    -> 简洁纯文本 (暂时我们主要用 structured)


ACTION_KEYWORDS = [
    "please",
    "rsvp",
    "reply",
    "respond",
    "sign",
    "complete",
    "fill out",
    "submit",
    "bring",
    "pay",
    "schedule",
    "register",
    "book",
]


def _detect_simple_action_item(body: str) -> str:
    """非常简单的关键词检测，用于 fallback 模式下给一点 hint。"""
    text = (body or "").lower()

    hits = [kw for kw in ACTION_KEYWORDS if kw in text]

    if not hits:
        return "None detected (simple fallback summary)."

    # 只要命中就给一个宽泛的 action 提示
    pretty_hits = [f"“{kw}”" for kw in hits[:3]]
    hit_str = ", ".join(pretty_hits)
    return f"Looks like there’s something you may need to do — this email mentions {hit_str}."


def _fallback_summary(subject: str, body: str, style: str = "structured") -> str:
    """当没有 key 或 OpenAI 调用失败时，用一个简单但结构化的摘要。"""
    snippet = (body or "").strip().replace("\n", " ")
    snippet = snippet[:200] + ("..." if len(snippet) > 200 else "")
    action_line = _detect_simple_action_item(body or "")

    if style == "minimal":
        # 简洁版
        return (
            f"Subject: {subject or '(no subject)'}\n\n"
            f"Key info: {snippet or 'No content.'}"
        )

    # 默认：带 emoji 的结构化版本
    return (
        "📋 Summary\n"
        f"- {snippet or 'No content.'}\n\n"
        "🕒 Key details\n"
        f"- Subject: {subject or '(no subject)'}\n\n"
        "✅ Action items\n"
        f"- {action_line}\n\n"
        "📅 Calendar\n"
        "- No explicit date/time parsing in fallback."
    )


def summarize_email(subject: str, body: str) -> str:
    """
    用 OpenAI 做摘要：
    - 有 OPENAI_API_KEY 且 SDK 正常 -> 调 GPT，返回结构化摘要
    - 没 key / SDK 或调用失败 -> 走 fallback，也用统一风格
    """
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print("[LLM] No OPENAI_API_KEY found, using fallback summary.")
        return _fallback_summary(subject, body, ASSISTANT_STYLE)

    if OpenAI is None:
        print("[LLM] openai SDK not available, using fallback summary.")
        return _fallback_summary(subject, body, ASSISTANT_STYLE)

    try:
        print("[LLM] Using OpenAI GPT for summarization.")

        client = OpenAI(api_key=api_key)

        if ASSISTANT_STYLE == "minimal":
            system_prompt = (
                "You are an assistant that summarizes emails for a very busy parent.\n"
                "Respond in plain text with this format:\n\n"
                "Subject: <subject>\n\n"
                "Key info: <1–3 short sentences focusing on dates, times, locations, and actions.>\n"
                "Keep it under 100 words. Do NOT invent information.\n"
            )
        else:
            # 默认 structured + emoji 风格
            system_prompt = (
                "You are an assistant that summarizes emails for a very busy parent.\n"
                "You MUST respond in this exact format (in English):\n\n"
                "📋 Summary\n"
                "- ...\n\n"
                "🕒 Key details\n"
                "- ...\n"
                "- ...\n\n"
                "✅ Action items\n"
                "- ... (or 'None')\n\n"
                "📅 Calendar\n"
                "- ... (describe any event that should go on a calendar, or 'None').\n\n"
                "Rules:\n"
                "- Keep it under 120 words in total.\n"
                "- Focus on dates, times, locations, and what the parent needs to do.\n"
                "- Do NOT invent information that is not in the email.\n"
            )

        user_content = f"Subject: {subject}\n\nBody:\n{body}"

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.2,
            max_tokens=260,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print("[LLM] Error calling OpenAI, falling back to simple summary:", repr(e))
        return _fallback_summary(subject, body, ASSISTANT_STYLE)