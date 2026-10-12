"""Dates as org-mode writes them (`<2026-10-12 Mon 10:00>`, `#+DATE:`) and as
the site shows them (`12 octobre 2026`)."""

import datetime
import re

_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")

_MONTHS = {
    "fr": ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"),
    "en": ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"),
}


def parse_date(text: str) -> datetime.date | None:
    """The first YYYY-MM-DD date in `text` (`<2026-10-01 Wed>`, `2026-10-01`…)."""
    m = _ISO_DATE.search(text)
    if not m:
        return None
    try:
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def human_date(date: datetime.date, lang: str = "en", time: str = "") -> str:
    """`12 octobre 2026` (fr), `October 12, 2026` (en), ISO otherwise; `time`
    (`10:00`, `10:00–11:00`) is appended when given."""
    months = _MONTHS.get(lang[:2].lower())
    if months is None:
        text = date.isoformat()
        return f"{text} {time}" if time else text
    month = months[date.month - 1]
    if lang[:2].lower() == "fr":
        text = f"{date.day} {month} {date.year}"
        return f"{text} à {time}" if time else text
    text = f"{month} {date.day}, {date.year}"
    return f"{text}, {time}" if time else text
