# email_assistant/services/llm_extractor.py
import os
import json
import re
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from dotenv import load_dotenv
import dateparser
from dateparser.search import search_dates

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

load_dotenv(".env")


def _clean_email_body(body: str) -> str:
    if not body:
        return ""

    lines = body.splitlines()
    cleaned_lines: List[str] = []
    skipping_forward_header = False

    for line in lines:
        stripped = line.strip()

        if "Forwarded message" in stripped or "Original Message" in stripped:
            skipping_forward_header = True
            continue

        if skipping_forward_header:
            if stripped == "":
                skipping_forward_header = False
            continue

        if re.match(r"^(From|To|Cc|Subject|Date):", stripped):
            continue

        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)

    if len(text) > 8000:
        text = text[:8000] + "\n\n[truncated]"

    return text or body.strip()


def _extract_links(body: str, max_links: int = 2) -> List[Dict[str, str]]:
    urls = re.findall(r"https?://[^\s)>\"']+", body or "")
    out: List[Dict[str, str]] = []
    seen = set()
    for u in urls:
        u = u.strip().rstrip(".,;")
        if not u or u in seen:
            continue
        seen.add(u)
        out.append({"label": "Link", "url": u})
        if len(out) >= max_links:
            break
    return out


def _dt_to_iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _guess_duration(subject: str, body: str) -> timedelta:
    s = (subject or "").lower()
    t = (body or "").lower()
    is_meeting = any(k in s for k in ["meet", "meeting", "sync", "call"]) or any(
        k in t for k in ["zoom", "google meet", "meet", "call"]
    )
    return timedelta(minutes=30) if is_meeting else timedelta(hours=2)


def _find_first_datetime(text: str) -> Optional[datetime]:
    if not text or not text.strip():
        return None

    settings = {
        "PREFER_DATES_FROM": "future",
        "RETURN_AS_TIMEZONE_AWARE": False,
        "RELATIVE_BASE": datetime.now(),
    }

    results = search_dates(text, settings=settings, add_detected_language=False)
    if not results:
        settings2 = dict(settings)
        settings2["PREFER_DATES_FROM"] = "current_period"
        results = search_dates(text, settings=settings2, add_detected_language=False)

    if not results:
        return None

    # take first hit
    _, dt = results[0]
    return dt


def _extract_location(text: str) -> str:
    if not text:
        return ""
    m = re.search(r"\b(at|in)\s+([A-Za-z0-9 ,#\-\(\)]+)", text)
    if not m:
        return ""
    return m.group(2).strip().rstrip(" .;,")


def _heuristic_calendar_event(subject: str, body: str) -> Optional[Dict[str, str]]:
    text = (body or "").strip()
    if not text:
        return None

    dt = _find_first_datetime(text)
    if not dt:
        return None

    end = dt + _guess_duration(subject, body)
    loc = _extract_location(text)

    return {
        "title": subject or "Event",
        "start_datetime": _dt_to_iso(dt),
        "end_datetime": _dt_to_iso(end),
        "timezone": "America/New_York",
        "location": loc,
        "description": "",
    }


def _fallback_forward_package(subject: str, body: str) -> Dict[str, Any]:
    clean = _clean_email_body(body or "")
    one_line = clean.replace("\n", " ").strip()
    snippet = one_line[:240] + ("…" if len(one_line) > 240 else "")

    links = _extract_links(body, max_links=2)

    cal = _heuristic_calendar_event(subject, body)
    has_cal = bool(cal and cal.get("start_datetime"))

    return {
        "category": "fyi",
        "forward_subject": f"{subject} – Key Info" if subject else "Fwd: Key Info",
        "tone": "short",
        "key_points": [snippet] if snippet else ["(No email content found.)"],
        "links": links,
        "has_calendar_event": has_cal,
        "calendar_event": cal
        or {
            "title": "",
            "start_datetime": "",
            "end_datetime": "",
            "timezone": "",
            "location": "",
            "description": "",
        },
    }


def _normalize_forward_pkg(data: Dict[str, Any], subject: str, raw_body: str) -> Dict[str, Any]:
    category = str(data.get("category", "") or "").strip() or "fyi"
    if category not in {"event", "scheduling", "action_required", "fyi", "billing", "recruiting", "personal"}:
        category = "fyi"

    tone = str(data.get("tone", "") or "").strip().lower() or "short"
    if tone not in {"short", "warm", "formal"}:
        tone = "short"

    forward_subject = str(data.get("forward_subject", "") or "").strip()
    if not forward_subject:
        forward_subject = f"{subject} – Key Info" if subject else "Fwd: Key Info"

    key_points = data.get("key_points") or []
    if not isinstance(key_points, list):
        key_points = []
    key_points = [str(x).strip() for x in key_points if str(x).strip()]
    key_points = key_points[:8] if key_points else []

    links = data.get("links") or []
    if not isinstance(links, list):
        links = []
    cleaned_links: List[Dict[str, str]] = []
    for item in links:
        if isinstance(item, dict):
            url = str(item.get("url", "") or "").strip()
            label = str(item.get("label", "") or "").strip() or "Link"
            if url:
                cleaned_links.append({"label": label, "url": url})
        if len(cleaned_links) >= 2:
            break
    if not cleaned_links:
        cleaned_links = _extract_links(raw_body, max_links=2)

    has_cal = bool(data.get("has_calendar_event", False))
    cal = data.get("calendar_event") or {}
    if not isinstance(cal, dict):
        cal = {}

    calendar_event = {
        "title": str(cal.get("title", "") or "").strip(),
        "start_datetime": str(cal.get("start_datetime", "") or "").strip(),
        "end_datetime": str(cal.get("end_datetime", "") or "").strip(),
        "timezone": str(cal.get("timezone", "") or "").strip(),
        "location": str(cal.get("location", "") or "").strip(),
        "description": str(cal.get("description", "") or "").strip(),
    }

    # If LLM didn't provide a usable start time, do heuristic extraction
    if not calendar_event["start_datetime"]:
        cal2 = _heuristic_calendar_event(subject, raw_body)
        if cal2:
            calendar_event = cal2
            has_cal = True
        else:
            has_cal = False

    if not key_points:
        clean = _clean_email_body(raw_body or "")
        one_line = clean.replace("\n", " ").strip()
        snippet = one_line[:240] + ("…" if len(one_line) > 240 else "")
        key_points = [snippet] if snippet else ["(No email content found.)"]

    return {
        "category": category,
        "forward_subject": forward_subject,
        "tone": tone,
        "key_points": key_points,
        "links": cleaned_links,
        "has_calendar_event": has_cal,
        "calendar_event": calendar_event,
    }


def build_forward_package(subject: str, body: str) -> Dict[str, Any]:
    subject = subject or ""
    raw_body = body or ""
    cleaned_body = _clean_email_body(raw_body)

    if not cleaned_body.strip():
        return _fallback_forward_package(subject, raw_body)

    api_key = os.getenv("OPENAI_API_KEY")
    if OpenAI is None or not api_key:
        return _fallback_forward_package(subject, raw_body)

    try:
        client: "OpenAI" = OpenAI(api_key=api_key)

        system_msg = f"""
You are an email forwarding assistant. Output ONLY valid JSON.

Today's date is {datetime.now().strftime('%A, %B %d, %Y')}.

JSON keys:
- category: one of [event, scheduling, action_required, fyi, billing, recruiting, personal]
- forward_subject: short subject for forwarding
- tone: one of [short, warm, formal]
- key_points: 4 to 8 bullets max
- links: up to 2 links, each {{label, url}}
- has_calendar_event: boolean (true only if date+time are clearly specified)
- calendar_event: {{title, start_datetime, end_datetime, timezone, location, description}}

Rules:
- Ignore greetings/signatures/boilerplate.
- If time is vague (e.g. next week, TBD), has_calendar_event must be false.
- If end time missing: meeting=30min, event=2h
"""

        resp = client.responses.create(
            model="gpt-5-mini",
            input=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"Subject: {subject}\n\nEmail:\n{cleaned_body}"},
            ],
            response_format={"type": "json_object"},
        )

        content_block = resp.output[0].content[0].text
        raw_text = getattr(content_block, "value", content_block)
        data = json.loads(raw_text)

        if not isinstance(data, dict):
            return _fallback_forward_package(subject, raw_body)

        return _normalize_forward_pkg(data, subject, raw_body)

    except Exception as e:
        print("[LLM] Error -> fallback:", repr(e))
        return _fallback_forward_package(subject, raw_body)