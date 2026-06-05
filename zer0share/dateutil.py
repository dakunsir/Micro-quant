from datetime import date, timedelta

_FMT = "%Y%m%d"


def _parse(s: str) -> date:
    return date(int(s[:4]), int(s[4:6]), int(s[6:]))


def today() -> str:
    return date.today().strftime(_FMT)


def add_days(s: str, n: int) -> str:
    return (_parse(s) + timedelta(days=n)).strftime(_FMT)


def month_ranges(start: str, end: str) -> list[tuple[str, str]]:
    s = _parse(start)
    e = _parse(end)
    ranges = []
    current = date(s.year, s.month, 1)
    while current <= e:
        if current.month == 12:
            next_month = date(current.year + 1, 1, 1)
        else:
            next_month = date(current.year, current.month + 1, 1)
        month_start = max(s, current)
        month_end = min(e, next_month - timedelta(days=1))
        ranges.append((month_start.strftime(_FMT), month_end.strftime(_FMT)))
        current = next_month
    return ranges


def week_ranges(start: str, end: str) -> list[tuple[str, str]]:
    s = _parse(start)
    e = _parse(end)
    weeks: list[tuple[str, str]] = []
    seen: set[tuple[int, int]] = set()
    current = s
    while current <= e:
        iso_year, iso_week, _ = current.isocalendar()
        week_key = (iso_year, iso_week)
        if week_key not in seen:
            seen.add(week_key)
            week_num = f"{iso_year}{iso_week:02d}"
            monday = current - timedelta(days=current.weekday())
            weeks.append((week_num, monday.strftime(_FMT)))
        current += timedelta(days=7)
    return weeks
