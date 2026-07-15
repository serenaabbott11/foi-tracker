import json
from datetime import date, timedelta
from pathlib import Path

HOLIDAYS_FILE = Path(__file__).with_name("bank-holidays.json")


def _load_holidays() -> frozenset[date]:
    # FOI Act 2000 s.10(6): a "working day" excludes any day that is a
    # bank holiday under the Banking and Financial Dealings Act 1971 in
    # *any* part of the United Kingdom. So we union the three divisions
    # gov.uk publishes (England & Wales, Scotland, Northern Ireland).
    data = json.loads(HOLIDAYS_FILE.read_text())
    return frozenset(
        date.fromisoformat(e["date"])
        for division in data.values()
        for e in division["events"]
    )


BANK_HOLIDAYS = _load_holidays()


def calculate_deadline(received: date) -> date:
    """Add 20 working days to the received date.

    Working days = Mon-Fri, excluding any day that is a bank holiday in
    any of the four UK nations (per FOI Act 2000 s.10(6)).
    """
    current = received
    added = 0
    while added < 20:
        current += timedelta(days=1)
        if current.weekday() < 5 and current not in BANK_HOLIDAYS:
            added += 1
    return current
