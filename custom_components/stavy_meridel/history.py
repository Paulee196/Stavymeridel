"""Monthly consumption, kept separate from publication-time sensor readings."""
from datetime import date, datetime, timedelta, timezone
import re

from .parser import normalized, parse_dashboard, period_from_header


def parse_history(payload, kind, today):
    """Use the same verified table schema as current readings."""
    periods = {period_from_header(h) for h in payload["measurementsTable"]["headers"]}
    result = {}
    for period in sorted(p for p in periods if p and p <= (today.year, today.month)):
        for reading in parse_dashboard(payload, kind, date(*period, 1)):
            key = f"{kind}_{reading.serial}"
            item = result.setdefault(key, {"serial": reading.serial, "kind": kind,
                                          "room": reading.room, "unit": reading.unit,
                                          "months": {}})
            item["months"][reading.period] = reading.value
    return result


def merge_history(archive, incoming):
    """Keep old years across rollovers; allow source corrections, including missing values."""
    for key, item in incoming.items():
        previous = archive.get(key, {}).get("months", {})
        valid = {period: value for period, value in item["months"].items() if value is not None}
        archive[key] = {**item, "months": {**previous, **valid}}


def previous_period(period):
    year, month = map(int, period.split("-"))
    if month == 1:
        return f"{year-1:04d}-12"
    return f"{year:04d}-{month-1:02d}"


def monthly_consumption(item):
    """Never spread a multi-month gap into one month or assume a water-meter reset."""
    result = {}
    for period, value in sorted(item["months"].items()):
        if value is None:
            continue
        previous = item["months"].get(previous_period(period))
        if (item["kind"] == 19 and normalized(item.get("unit", "")).startswith("dil")
                and period.endswith("-01")):
            # Heat allocators shown by this portal reset their count every January.
            delta = value
        elif previous is None:
            continue
        else:
            delta = value - previous
        if delta >= 0:
            result[period] = round(delta, 6)
    return result


def history_issue(item):
    """A counter decrease outside a known reset needs inspection, not an inferred consumption."""
    for period, value in item["months"].items():
        previous = item["months"].get(previous_period(period))
        reset = (item["kind"] == 19 and normalized(item.get("unit", "")).startswith("dil")
                 and period.endswith("-01"))
        if value is not None and previous is not None and value < previous and not reset:
            return "counter_decreased"
    return None


def statistic_id(code, key):
    """Stable IDs independent of HA's generated entity IDs."""
    safe_key = re.sub(r"[^a-z0-9_]", "_", key.lower())
    return f"stavy_meridel:byt_{code}_{safe_key}"


def statistics_rows(consumption, tz, now):
    """One replaceable monthly bucket; no fabricated daily/hourly distribution.

    Each month's amount is assigned to its first local hour. Re-importing replaces
    that bucket, including the provisional current month, rather than appending it.
    The preceding hour establishes a zero baseline for HA's change calculations.
    """
    rows = []
    total = 0.0
    for period, amount in sorted(consumption.items()):
        year, month = map(int, period.split("-"))
        start = datetime(year, month, 1, tzinfo=tz).astimezone(timezone.utc)
        if start + timedelta(hours=1) > now:
            continue
        if not rows:
            rows.append({"start": start - timedelta(hours=1), "sum": 0.0})
        total = round(total + amount, 6)
        rows.append({"start": start, "sum": total})
    return rows
