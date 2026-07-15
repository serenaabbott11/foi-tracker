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
    # Maundy Thursday (Thu 2 Apr 2026) is not a bank holiday in any UK
    # nation, so it counts as a working day. A request received
    # Wed 4 Mar 2026 has its 20th working day land on it — the count
    # correctly skips Tue 17 Mar (St Patrick's Day, NI) along the way.
    assert calculate_deadline(date(2026, 3, 4)) == date(2026, 4, 2)


def test_scotland_2nd_january_2026_extends_deadline():
    # FOI Act s.10(6) treats "any part of the UK" bank holidays as
    # non-working days. 2nd January 2026 (Fri) is a Scotland-only bank
    # holiday. Received Tue 30 Dec 2025 → deadline Thu 29 Jan 2026;
    # if 2 Jan were counted (old E&W-only logic) it would be Wed 28 Jan.
    assert calculate_deadline(date(2025, 12, 30)) == date(2026, 1, 29)
