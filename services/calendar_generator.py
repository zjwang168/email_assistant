# services/calendar_generator.py
import re
from datetime import datetime, timedelta

import dateparser


def extract_event_info(subject: str, body: str):
    """
    从邮件正文里尽量提取一个事件：
    - start_datetime: 用 dateparser 从整段文本里找第一个日期+时间
    - end_datetime: 默认 +1 小时
    - location: 简单从 'in Room 210' 或 'at XXX' 这种结构里抓
    """
    text = (body or "").strip()

    # 1) 用 dateparser 找时间（偏向未来）
    dt = dateparser.parse(
        text,
        settings={
            "PREFER_DATES_FROM": "future",
            "RETURN_AS_TIMEZONE_AWARE": False,
        },
    )

    if not dt:
        return None  # 没找到时间就认为没事件

    start = dt
    end = dt + timedelta(hours=1)

    # 2) 尝试找地点：in Room 210 / at Room 210 / at the library 等
    location = ""
    loc_match = re.search(r"\b(in|at)\s+([A-Za-z0-9 ,#\-]+)", text)
    if loc_match:
        location = loc_match.group(2).strip().rstrip(".")

    return {
        "start": start,
        "end": end,
        "location": location,
        "subject": subject or "Event",
    }


def generate_ics_content(subject: str, event_info: dict) -> str:
    """
    根据事件信息生成 .ics 内容（字符串），由 mail_sender 作为附件发送
    """
    uid = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    now_utc = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    fmt = "%Y%m%dT%H%M%SZ"
    dtstart = event_info["start"].strftime(fmt)
    dtend = event_info["end"].strftime(fmt)

    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Zijin Assistant//EN
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{now_utc}
DTSTART:{dtstart}
DTEND:{dtend}
SUMMARY:{subject}
LOCATION:{event_info.get('location', '')}
END:VEVENT
END:VCALENDAR
"""
    return ics_content


def detect_event_and_build_ics(subject: str, body: str) -> str | None:
    """
    综合入口：从正文里检测事件，若有则生成 .ics 字符串并返回；否则返回 None。
    """
    event_info = extract_event_info(subject, body)
    if not event_info:
        return None

    return generate_ics_content(subject, event_info)