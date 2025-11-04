# services/llm_extractor.py
import os
from dotenv import load_dotenv

# 确保 .env 被读到（双保险，main.py 里也有一次没问题）
load_dotenv(".env")

try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # 如果 openai 包没装或有问题，就直接走 fallback


def _fallback_summary(subject: str, body: str) -> str:
    """当没有 key 或 OpenAI 调用失败时，用一个简单安全的摘要。"""
    snippet = (body or "").strip().replace("\n", " ")
    snippet = snippet[:200] + ("..." if len(snippet) > 200 else "")
    return f"Subject: {subject}\n\nKey info: {snippet}"


def summarize_email(subject: str, body: str) -> str:
    """
    用 OpenAI 做摘要：
    - 如果没有 OPENAI_API_KEY 或 SDK、有问题 → 自动回退到简单摘要
    - 任何异常都不让 FastAPI 500
    """
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        print("[LLM] No OPENAI_API_KEY found, using fallback summary.")
        return _fallback_summary(subject, body)

    if OpenAI is None:
        print("[LLM] openai SDK not available, using fallback summary.")
        return _fallback_summary(subject, body)

    try:
        print("[LLM] Using OpenAI GPT for summarization.")

        # 每次在这里创建 client，避免 import 阶段出问题
        client = OpenAI(api_key=api_key)

        system_prompt = (
            "You are an assistant that summarizes emails for a very busy parent.\n"
            "Your job is to:\n"
            "- Pull out key dates, times, locations, and action items\n"
            "- Use plain, friendly language\n"
            "- Keep it under 3 short bullet points\n"
            "- If there is something to add to a calendar, say it explicitly\n"
        )

        user_content = f"Subject: {subject}\n\nBody:\n{body}"

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.2,
            max_tokens=220,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        # ⭐ 关键点：不管 OpenAI 抛什么错，都只打印，然后走 fallback
        print("[LLM] Error calling OpenAI, falling back to simple summary:", repr(e))
        return _fallback_summary(subject, body)