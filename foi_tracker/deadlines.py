import json
from datetime import date, timedelta
from pathlib import Path

HOLIDAYS_FILE = Path(__file__).with_name("bank-holidays.json")


def _load_holidays() -> frozenset[date]:
    data = json.loads(HOLIDAYS_FILE.read_text())
    return frozenset(
        date.fromisoformat(e["date"]) for e in data["england-and-wales"]["events"]
    )


BANK_HOLIDAYS = _load_holidays()


def calculate_deadline(received: date) -> date:
    """Add 20 working days to the received date.

    Working days = Mon-Fri, excluding England & Wales bank holidays.
    """
    current = received
    added = 0
    while added < 20:
        current += timedelta(days=1)
        if current.weekday() < 5 and current not in BANK_HOLIDAYS:
            added += 1
    return current
