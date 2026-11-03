"""Strict parser based on the portal's public table renderer, without HA imports."""
from dataclasses import dataclass
from datetime import date
import math
import re
import unicodedata


class SchemaError(Exception):
    """The server response cannot be interpreted safely."""


@dataclass(frozen=True)
class Reading:
    serial: str
    room: str
    value: float | None
    period: str
    kind: int
    unit: str


def plain(value):
    """Unwrap the extended cells used by the portal."""
    return value.get("value") if isinstance(value, dict) else value


def normalized(value):
    return "".join(c for c in unicodedata.normalize("NFKD", str(value)).lower()
                   if not unicodedata.combining(c))


def canonical_unit(kind, unit):
    """Normalize spelling only; never convert allocator counts into energy."""
    unit = "" if unit is None else str(unit).strip()
    if kind in (2, 4):
        if unit.replace(" ", "").replace("\u00a0", "").lower() not in ("m³", "m3", "m^3"):
            raise SchemaError("Unverified water unit")
        return "m³"
    if normalized(unit) in ("dil", "dilek", "dilky", "dilku"):
        return "dílky"
    if not unit:
        raise SchemaError("Missing heat unit")
    return unit


def number(value):
    value = plain(value)
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise SchemaError("Boolean in a numeric cell")
    try:
        parsed = float(str(value).replace("\u00a0", "").replace(" ", "").replace(",", "."))
    except (ValueError, TypeError) as err:
        raise SchemaError("Invalid numeric cell") from err
    if not math.isfinite(parsed) or parsed < 0:
        raise SchemaError("Invalid meter reading")
    return parsed


MONTHS = ("leden", "unor", "brezen", "duben", "kveten", "cerven", "cervenec",
          "srpen", "zari", "rijen", "listopad", "prosinec")


def period_from_header(header):
    """Recognize explicit months; never use a numeric metadata cell as a reading."""
    label = normalized(header.get("label", "")).strip()
    match = re.fullmatch(r"(20\d{2})[-/.](0?[1-9]|1[0-2])", label)
    if match:
        return int(match[1]), int(match[2])
    match = re.fullmatch(r"(0?[1-9]|1[0-2])[/.\s]+(20\d{2})", label)
    if match:
        return int(match[2]), int(match[1])
    match = re.fullmatch(r"([a-z]+)\s+(20\d{2})", label)
    if match and match[1] in MONTHS:
        return int(match[2]), MONTHS.index(match[1]) + 1
    return None


def cell(row, key):
    value = row
    for part in key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return plain(value)


def parse_dashboard(payload, kind, today=None):
    """Return current-month/latest available columns, including missing values."""
    if not isinstance(payload, dict) or payload.get("error"):
        raise SchemaError("Dashboard unavailable")
    table = payload.get("measurementsTable")
    if not isinstance(table, dict):
        raise SchemaError("Missing measurementsTable")
    headers, rows = table.get("headers"), table.get("rows")
    if not isinstance(headers, list) or not isinstance(rows, list):
        raise SchemaError("Invalid table")
    if not rows:
        return []
    if not all(isinstance(h, dict) and isinstance(h.get("key"), str) for h in headers):
        raise SchemaError("Invalid headers")
    today = today or date.today()
    candidates = [(period_from_header(h), h["key"]) for h in headers]
    candidates = [(period, key) for period, key in candidates
                  if period is not None and period <= (today.year, today.month)]
    if not candidates:
        raise SchemaError("No recognized monthly column")
    period, key = max(candidates)
    room_key = next((h["key"] for h in headers
                     if normalized(h.get("label", "")).strip() == "mistnost"), None)
    unit = canonical_unit(kind, payload.get("consumptionUnits", ""))
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise SchemaError("Invalid row")
        serial = cell(row, "sn")
        if serial is None or str(serial) == "" or str(serial) in seen:
            raise SchemaError("Missing or duplicate serial")
        seen.add(str(serial))
        # Portal marks removed meters with a trash icon. Do not create active sensors for them.
        if isinstance(row.get("stav"), dict) and row["stav"].get("icon") == "trash":
            continue
        value = number(cell(row, key))
        if isinstance(row.get("stav"), dict) and row["stav"].get("icon") == "error":
            value = None
        result.append(Reading(str(serial), str(cell(row, room_key) or "") if room_key else "",
                              value, f"{period[0]:04d}-{period[1]:02d}", kind, unit))
    return result
