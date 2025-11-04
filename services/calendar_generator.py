# services/calendar_generator.py
from datetime import datetime, timedelta
import uuid


def generate_basic_ics(
    summary: str,
    description: str,
    start_time: datetime,
    duration_minutes: int = 60,
    location: str | None = None,
) -> str:
    """
    生成一个简单的 .ics 文本（返回字符串）。
    后面可以写到文件里当附件发出去。
    """

    end_time = start_time + timedelta(minutes=duration_minutes)

    def fmt(dt: datetime) -> str:
        # ics 用的是 UTC 格式，这里简单用本地时间当作 UTC（MVP 阶段先不纠结时区）
        return dt.strftime("%Y%m%dT%H%M%SZ")

    uid = str(uuid.uuid4())

    ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Zijin Email Assistant//EN
CALSCALE:GREGORIAN
BEGIN:VEVENT
UID:{uid}
SUMMARY:{summary}
DESCRIPTION:{description}
DTSTART:{fmt(start_time)}
DTEND:{fmt(end_time)}
"""

    if location:
        ics_content += f"LOCATION:{location}\n"

    ics_content += "END:VEVENT\nEND:VCALENDAR\n"

    return ics_content