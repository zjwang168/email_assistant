# email_assistant/services/calendar_generator.py
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple

import dateparser
from dateparser.search import search_dates


def _guess_duration(subject: str, body: str) -> timedelta:
    s = (subject or "").lower()
    t = (body or "").lower()
    is_meeting = any(k in s for k in ["meet", "meeting", "sync", "call"]) or any(
        k in t for k in ["zoom", "google meet", "meet", "call"]
    )
    return timedelta(minutes=30) if is_meeting else timedelta(hours=2)


def _extract_location(text: str) -> str:
    if not text:
        return ""
    m = re.search(r"\b(?:at|in)\s+([A-Za-z0-9 ,#\-\(\)]+)", text)
    if not m:
        return ""
    return m.group(1).strip().rstrip(" .;,")


def _find_first_datetime(text: str) -> Optional[datetime]:
    if not text or not text.strip():
        return None

    settings = {
        "PREFER_DATES_FROM": "future",
        "RETURN_AS_TIMEZONE_AWARE": False,
        "RELATIVE_BASE": datetime.now(),
    }

    results: Optional[List[Tuple[str, datetime]]] = search_dates(
        text,
        settings=settings,
        add_detected_language=False,
    )

    if not results:
        settings2 = dict(settings)
        settings2["PREFER_DATES_FROM"] = "current_period"
        results = search_dates(
            text,
            settings=settings2,
            add_detected_language=False,
        )

    if not results:
        return None

    _, dt = results[0]
    return dt


def detect_event(subject: str, body: str) -> Optional[Dict[str, Any]]:
    """
    Detect a concrete date+time in the email body.
    """
    text = (body or "").strip()
    dt = _find_first_datetime(text)
    if not dt:
        return None

    duration = _guess_duration(subject, body)
    end = dt + duration
    location = _extract_location(text)

    return {
        "title": subject or "Event",
        "start": dt,
        "end": end,
        "location": location,
        "description": "",
    }


def _dt_to_ics(dt: datetime) -> str:
    # MVP: emit as Zulu format without strict TZ conversion
    return dt.strftime("%Y%m%dT%H%M%SZ")


def build_ics_from_event(event: Dict[str, Any]) -> str:
    uid = datetime.utcnow().strftime("%Y%m%dT%H%M%S") + "@zijin-assistant"
    now_utc = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    dtstart = _dt_to_ics(event["start"])
    dtend = _dt_to_ics(event["end"])

    summary = (event.get("title") or "Event").replace("\n", " ").strip()
    location = (event.get("location") or "").replace("\n", " ").strip()
    description = (event.get("description") or "").replace("\n", " ").strip()

    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Zijin Assistant//EN
CALSCALE:GREGORIAN
METHOD:PUBLISH
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{now_utc}
DTSTART:{dtstart}
DTEND:{dtend}
SUMMARY:{summary}
LOCATION:{location}
DESCRIPTION:{description}
END:VEVENT
END:VCALENDAR
"""


def detect_event_and_build_ics(subject: str, body: str) -> Optional[str]:
    """
    Convenience wrapper used by main.py (fallback mode).
    """
    event = detect_event(subject, body)
    if not event:
        return None
    return build_ics_from_event(event)


def build_ics_from_calendar_event(calendar_event: Dict[str, Any]) -> Optional[str]:
    """
    Build ICS from LLM structured calendar_event if present.
    Expected keys: title, start_datetime, end_datetime, location, description
    """
    if not isinstance(calendar_event, dict):
        return None

    title = (calendar_event.get("title") or "").strip() or "Event"
    start_s = (calendar_event.get("start_datetime") or "").strip()
    end_s = (calendar_event.get("end_datetime") or "").strip()
    location = (calendar_event.get("location") or "").strip()
    description = (calendar_event.get("description") or "").strip()

    if not start_s:
        return None

    start_dt = dateparser.parse(start_s)
    if not start_dt:
        return None

    end_dt = dateparser.parse(end_s) if end_s else (start_dt + timedelta(minutes=30))

    event = {
        "title": title,
        "start": start_dt,
        "end": end_dt,
        "location": location,
        "description": description,
    }
    return build_ics_from_event(event)