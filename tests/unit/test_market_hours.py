from datetime import datetime, timedelta, timezone

from src.core.time_filter.market_hours import (
    FUNDING_TIMES_UTC,
    PRIMARY_PRIORITY,
    SESSION_WINDOWS,
    TradingSession,
    get_active_sessions,
    get_primary_session,
    is_in_session,
    minutes_to_next_funding,
)


def utc(h: int, m: int = 0, weekday: int = 0) -> datetime:
    """weekday=0(월)~6(일). 2024-01-01(월) 기준."""
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return base + timedelta(days=weekday, hours=h, minutes=m)


# ── 상수 구조 확인 ─────────────────────────────────────────────

def test_session_windows_constant_exists():
    assert len(SESSION_WINDOWS) == 4


def test_funding_times_constant_exists():
    assert (0, 0) in FUNDING_TIMES_UTC
    assert (8, 0) in FUNDING_TIMES_UTC
    assert (16, 0) in FUNDING_TIMES_UTC


def test_primary_priority_first_is_overlap():
    assert PRIMARY_PRIORITY[0] == TradingSession.OVERLAP


# ── is_in_session ───────────────────────────────────────────────

def test_is_in_session_seoul_start():
    w = next(s for s in SESSION_WINDOWS if s.name == TradingSession.SEOUL)
    assert is_in_session(utc(0, 0), w) is True


def test_is_in_session_seoul_end():
    w = next(s for s in SESSION_WINDOWS if s.name == TradingSession.SEOUL)
    assert is_in_session(utc(5, 59), w) is True


def test_is_in_session_after_seoul():
    w = next(s for s in SESSION_WINDOWS if s.name == TradingSession.SEOUL)
    assert is_in_session(utc(6, 0), w) is False


# ── get_active_sessions ─────────────────────────────────────────

def test_seoul_active_weekday():
    assert TradingSession.SEOUL in get_active_sessions(utc(1, 0, 0))


def test_seoul_active_weekend():
    assert TradingSession.SEOUL in get_active_sessions(utc(1, 0, 5))


def test_seoul_end_boundary():
    assert TradingSession.SEOUL in get_active_sessions(utc(5, 59))


def test_closed_gap():
    active = get_active_sessions(utc(6, 0))
    assert TradingSession.SEOUL not in active
    assert TradingSession.LONDON not in active
    assert TradingSession.NY not in active
    assert TradingSession.OVERLAP not in active


def test_london_active_weekday():
    assert TradingSession.LONDON in get_active_sessions(utc(12, 0, 0))


def test_london_active_weekend():
    assert TradingSession.LONDON in get_active_sessions(utc(12, 0, 6))


def test_overlap_contains_london_ny():
    active = get_active_sessions(utc(14, 0))
    assert TradingSession.LONDON in active
    assert TradingSession.NY in active
    assert TradingSession.OVERLAP in active


def test_closed_returns_closed_list():
    active = get_active_sessions(utc(23, 0))
    assert active == [TradingSession.CLOSED]


# ── get_primary_session ────────────────────────────────────────

def test_overlap_primary_from_list():
    active = get_active_sessions(utc(14, 0))
    assert get_primary_session(active) == TradingSession.OVERLAP


def test_overlap_primary_from_datetime():
    assert get_primary_session(utc(14, 0)) == TradingSession.OVERLAP


def test_overlap_primary_weekend():
    active = get_active_sessions(utc(14, 0, 5))
    assert get_primary_session(active) == TradingSession.OVERLAP


def test_closed_primary():
    active = get_active_sessions(utc(6, 30))
    assert get_primary_session(active) == TradingSession.CLOSED


def test_seoul_primary():
    active = get_active_sessions(utc(2, 0))
    assert get_primary_session(active) == TradingSession.SEOUL


# ── minutes_to_next_funding ────────────────────────────────────

def test_minutes_to_next_funding_before_midnight():
    dt = datetime(2024, 1, 1, 23, 50, tzinfo=timezone.utc)
    assert minutes_to_next_funding(dt) == 10.0


def test_minutes_to_next_funding_before_08():
    dt = datetime(2024, 1, 1, 7, 45, tzinfo=timezone.utc)
    assert minutes_to_next_funding(dt) == 15.0


def test_minutes_to_next_funding_always_positive():
    for h in range(24):
        dt = datetime(2024, 1, 1, h, 0, tzinfo=timezone.utc)
        assert minutes_to_next_funding(dt) > 0

