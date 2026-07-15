# Deadline calculation for FOI requests.
# The Freedom of Information Act says responses are due within
# 20 working days. Working days = not Saturday or Sunday.

from datetime import date, timedelta


def calculate_deadline(received: date) -> date:
    """Add 20 working days to the received date."""
    current = received
    added = 0
    while added < 20:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Mon-Fri
            added += 1
    return current
