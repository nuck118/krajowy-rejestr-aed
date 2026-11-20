import re
from datetime import datetime
from zoneinfo import ZoneInfo

WARSAW_TZ = ZoneInfo("Europe/Warsaw")

DAY_INDEX = {
    "mo": 0,
    "tu": 1,
    "we": 2,
    "th": 3,
    "fr": 4,
    "sa": 5,
    "su": 6,
}

DAY_RANGE_RE = re.compile(r"\b(mo|tu|we|th|fr|sa|su)(?:-(mo|tu|we|th|fr|sa|su))?\b", re.IGNORECASE)
TIME_RANGE_RE = re.compile(r"(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})")


def _parse_days(spec: str) -> set[int]:
    days: set[int] = set()
    for match in DAY_RANGE_RE.finditer(spec):
        start = DAY_INDEX[match.group(1).lower()]
        end_key = match.group(2)
        if end_key is None:
            days.add(start)
        else:
            end = DAY_INDEX[end_key.lower()]
            if start <= end:
                days.update(range(start, end + 1))
            else:
                days.update(range(start, 7))
                days.update(range(0, end + 1))
    return days


def _minutes_since_midnight(hour: int, minute: int) -> int:
    return hour * 60 + minute


def _in_time_spans(spans: list[tuple[int, int]], current_min: int) -> bool:
    for start_min, end_min in spans:
        if start_min <= end_min:
            if start_min <= current_min <= end_min:
                return True
        else:
            # Overnight interval e.g. 05:00-00:30 or 20:00-06:00
            if current_min >= start_min or current_min <= end_min:
                return True
    return False


def is_open_now(
    opening_hours: str | None,
    is_24_7: bool = False,
    now: datetime | None = None,
) -> bool | None:
    if is_24_7:
        return True
    if not opening_hours:
        return None

    raw = opening_hours.strip()
    if not raw:
        return None
    if raw.lower() == "24/7":
        return True

    local_now = (
        now.astimezone(WARSAW_TZ)
        if now and now.tzinfo
        else (now.replace(tzinfo=WARSAW_TZ) if now else datetime.now(WARSAW_TZ))
    )
    weekday = local_now.weekday()
    current_min = local_now.hour * 60 + local_now.minute

    rules = [r.strip() for r in raw.split(";") if r.strip()]
    matched_state: bool | None = None
    parsed_any_rule = False

    for rule in rules:
        lower_rule = rule.lower()
        days = _parse_days(rule)
        if "off" in lower_rule or "closed" in lower_rule:
            if days:
                parsed_any_rule = True
                if weekday in days:
                    matched_state = False
            continue

        spans: list[tuple[int, int]] = []
        for tm in TIME_RANGE_RE.finditer(rule):
            sh, sm, eh, em = int(tm.group(1)), int(tm.group(2)), int(tm.group(3)), int(tm.group(4))
            spans.append((_minutes_since_midnight(sh, sm), _minutes_since_midnight(eh, em)))

        if not spans:
            continue

        parsed_any_rule = True
        # If no day selector specified (e.g. "08:00-20:00"), applies every day
        applies_today = (weekday in days) if days else True
        if applies_today:
            matched_state = _in_time_spans(spans, current_min)
        elif matched_state is None:
            matched_state = False

    if not parsed_any_rule:
        return None
    return matched_state
