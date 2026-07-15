from datetime import date

from foi_tracker.deadlines import calculate_deadline


def test_easter_2026_skips_good_friday_and_easter_monday():
    # Received Fri 27 Mar 2026, spans Good Fri (3 Apr) and Easter Mon (6 Apr).
    assert calculate_deadline(date(2026, 3, 27)) == date(2026, 4, 28)


def test_christmas_2026_skips_christmas_and_boxing_day():
    # Received Tue 1 Dec 2026, spans Christmas Day (Fri 25 Dec) and
    # Boxing Day observed (Mon 28 Dec).
    assert calculate_deadline(date(2026, 12, 1)) == date(2026, 12, 31)


def test_august_bank_holiday_2026_foi_0188():
    # FOI-2026-0188 received Thu 20 Aug 2026 — Summer bank holiday is
    # Mon 31 Aug 2026, so the deadline shifts from 17 Sep to 18 Sep.
    assert calculate_deadline(date(2026, 8, 20)) == date(2026, 9, 18)


def test_maundy_thursday_2026_is_a_working_day():
    # Maundy Thursday (Thu 2 Apr 2026) is not a bank holiday in
    # England & Wales, so it counts as a normal working day. A request
    # received Thu 5 Mar 2026 has its 20th working day land on it.
    assert calculate_deadline(date(2026, 3, 5)) == date(2026, 4, 2)
