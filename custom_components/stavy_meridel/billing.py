"""Prices effective from a calendar month and comparable completed periods."""
from .history import monthly_consumption
import math
from datetime import date


def price_for_month(tariffs, kind, period):
    candidates = [t for t in tariffs if t["kind"] == kind and t["from"] <= period]
    return max(candidates, key=lambda t: t["from"])["price"] if candidates else None


def monthly_costs(item, tariffs):
    costs = {}
    for period, amount in monthly_consumption(item).items():
        price = price_for_month(tariffs, item["kind"], period)
        if price is not None:
            costs[period] = round(amount * price, 6)
    return costs


def set_tariff(tariffs, kind, period, price):
    """Adding an existing type/month edits that price without deleting older rates."""
    if isinstance(price, bool) or not math.isfinite(price) or price < 0:
        raise ValueError("Invalid price")
    items = [t for t in tariffs if (t["kind"], t["from"]) != (kind, period)]
    items.append({"kind": kind, "from": period, "price": price})
    return sorted(items, key=lambda t: (t["kind"], t["from"]))


def editor_date(options, today):
    """The selected month affects only prices subsequently entered by the user."""
    value = date.fromisoformat(options["price_editor_date"]) if options.get("price_editor_date") else today.replace(day=1)
    if value.day != 1:
        raise ValueError("Select the first day of a month")
    return value


def price_control_options(options, kind, value, today, currency):
    """Edit a single price in the selected month, retaining every other setting."""
    period = editor_date(options, today).strftime("%Y-%m")
    return {**options,
            "tariffs": set_tariff(options.get("tariffs", []), kind, period, value),
            "tariff_currency": options.get("tariff_currency", currency)}


def compare_years(item, today):
    """Compare only matching completed months, not a partial month with last year's full month."""
    amounts = monthly_consumption(item)
    pairs = [(f"{today.year}-{month:02d}", f"{today.year-1}-{month:02d}")
             for month in range(1, today.month)]
    pairs = [(current, previous) for current, previous in pairs
             if current in amounts and previous in amounts]
    if not pairs:
        return {"current": None, "previous": None, "percent": None, "months": [],
                "complete": False}
    current = round(sum(amounts[a] for a, _ in pairs), 6)
    previous = round(sum(amounts[b] for _, b in pairs), 6)
    return {"current": current, "previous": previous,
            "percent": round((current - previous) / previous * 100, 2) if previous else None,
            "months": [int(a[-2:]) for a, _ in pairs],
            "complete": len(pairs) == today.month - 1}
