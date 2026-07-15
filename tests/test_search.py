"""Search tests: matches every text column, case-insensitive, trimmed."""


def _refs(rows):
    return {r["ref"] for r in rows}


def test_empty_query_returns_all_rows(client):
    rows = client.get("/api/requests").get_json()
    assert len(rows) == 5


def test_whitespace_only_query_returns_all_rows(client):
    rows = client.get("/api/requests?q=   ").get_json()
    assert len(rows) == 5


def test_search_matches_by_ref(client):
    rows = client.get("/api/requests?q=FOI-2026-0003").get_json()
    assert _refs(rows) == {"FOI-2026-0003"}


def test_search_matches_by_requester(client):
    rows = client.get("/api/requests?q=Cycling").get_json()
    assert _refs(rows) == {"FOI-2026-0004"}


def test_search_matches_by_subject(client):
    rows = client.get("/api/requests?q=Thames").get_json()
    assert _refs(rows) == {"FOI-2026-0002"}


def test_search_matches_by_status(client):
    rows = client.get("/api/requests?q=Overdue").get_json()
    assert _refs(rows) == {"FOI-2026-0004"}


def test_search_matches_by_notes(client):
    rows = client.get("/api/requests?q=minister").get_json()
    assert _refs(rows) == {"FOI-2026-0004"}


def test_search_matches_by_received_date(client):
    rows = client.get("/api/requests?q=2026-01-10").get_json()
    assert _refs(rows) == {"FOI-2026-0003"}


def test_search_matches_by_deadline_date(client):
    rows = client.get("/api/requests?q=2026-02-17").get_json()
    assert _refs(rows) == {"FOI-2026-0005"}


def test_search_is_case_insensitive(client):
    upper = client.get("/api/requests?q=BRIDGES").get_json()
    lower = client.get("/api/requests?q=bridges").get_json()
    mixed = client.get("/api/requests?q=BrIdGeS").get_json()
    assert _refs(upper) == _refs(lower) == _refs(mixed) == {"FOI-2026-0001"}


def test_search_trims_whitespace(client):
    padded = client.get("/api/requests?q=  Thames  ").get_json()
    tight = client.get("/api/requests?q=Thames").get_json()
    assert _refs(padded) == _refs(tight) == {"FOI-2026-0002"}


def test_search_returns_multiple_matches(client):
    # "2026" appears in every ref and every date
    rows = client.get("/api/requests?q=2026").get_json()
    assert len(rows) == 5


def test_search_no_match_returns_empty_list(client):
    rows = client.get("/api/requests?q=nothing-matches-this-string").get_json()
    assert rows == []


def test_search_partial_match_by_substring(client):
    rows = client.get("/api/requests?q=Herald").get_json()
    assert _refs(rows) == {"FOI-2026-0005"}
