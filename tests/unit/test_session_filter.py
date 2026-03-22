from datetime import datetime, timedelta, timezone

from src.core.time_filter.session_filter import SessionFilter


# 명세 지시: SessionFilter()는 인수 없이 초기화 가능해야 한다
sf = SessionFilter()


def utc(h: int, m: int = 0, weekday: int = 0) -> datetime:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    return base + timedelta(days=weekday, hours=h, minutes=m)


# ── check() 반환 dict 구조 확인 ───────────────────────────────

def test_result_keys():
    r = sf.check(utc(10, 0))
    for key in ["allowed", "primary_session", "active_sessions", "reason", "checked_ts_utc"]:
        assert key in r


def test_active_sessions_is_list():
    r = sf.check(utc(14, 0))
    assert isinstance(r["active_sessions"], list)


def test_checked_ts_utc_is_str():
    r = sf.check(utc(10, 0))
    assert isinstance(r["checked_ts_utc"], str)


# ── SEOUL 세션 ───────────────────────────────────────────────

def test_seoul_allowed_weekday():
    r = sf.check(utc(1, 0, 0))
    assert r["allowed"] is True
    assert r["primary_session"] == "SEOUL"
    assert r["reason"] == "allowed_session"


def test_seoul_allowed_weekend():
    r = sf.check(utc(1, 0, 5))  # 토요일
    assert r["allowed"] is True
    assert r["primary_session"] == "SEOUL"


def test_seoul_end_boundary():
    r = sf.check(utc(5, 59))
    assert r["primary_session"] == "SEOUL"


# ── CLOSED 구간 ───────────────────────────────────────────────

def test_closed_after_seoul():
    r = sf.check(utc(6, 0))
    assert r["allowed"] is False
    assert r["primary_session"] == "CLOSED"
    assert r["reason"] == "outside_allowed_session"


def test_closed_late_night():
    r = sf.check(utc(23, 0))
    assert r["allowed"] is False
    assert r["primary_session"] == "CLOSED"


# ── LONDON 세션 ───────────────────────────────────────────────

def test_london_weekday():
    r = sf.check(utc(12, 0, 0))
    assert "LONDON" in r["active_sessions"]


def test_london_weekend():
    r = sf.check(utc(12, 0, 6))  # 일요일
    assert "LONDON" in r["active_sessions"]


# ── OVERLAP 세션 ──────────────────────────────────────────────

def test_overlap_primary_weekday():
    r = sf.check(utc(14, 0, 0))
    assert r["primary_session"] == "OVERLAP"


def test_overlap_primary_weekend():
    r = sf.check(utc(14, 0, 5))  # 토요일
    assert r["primary_session"] == "OVERLAP"


# ── is_allowed ────────────────────────────────────────────────

def test_is_allowed_seoul():
    assert sf.is_allowed(utc(1, 0)) is True


def test_is_allowed_closed():
    assert sf.is_allowed(utc(6, 30)) is False


# ── get_primary_session ───────────────────────────────────────

def test_get_primary_session_returns_str():
    ps = sf.get_primary_session(utc(14, 0))
    assert isinstance(ps, str)
    assert ps == "OVERLAP"


# ── get_effective_entry_score_min ─────────────────────────────

def test_entry_score_seoul_is_80():
    score = sf.get_effective_entry_score_min(utc(1, 0))  # SEOUL
    assert score == 80


def test_entry_score_london_is_70():
    score = sf.get_effective_entry_score_min(utc(12, 0))  # LONDON
    assert score == 70


def test_entry_score_seoul_higher_than_london():
    seoul = sf.get_effective_entry_score_min(utc(1, 0))
    london = sf.get_effective_entry_score_min(utc(12, 0))
    assert seoul > london


# ── minutes_to_next_funding ───────────────────────────────────

def test_minutes_to_next_funding_positive():
    for h in range(24):
        dt = datetime(2024, 1, 1, h, 0, tzinfo=timezone.utc)
        assert sf.minutes_to_next_funding(dt) > 0


def test_minutes_to_next_funding_before_08():
    dt = datetime(2024, 1, 1, 7, 45, tzinfo=timezone.utc)
    assert sf.minutes_to_next_funding(dt) == 15.0


# ── reason 규칙 확인 ───────────────────────────────────────────

def test_reason_allowed_session():
    r = sf.check(utc(12, 0))
    assert r["reason"] == "allowed_session"


def test_reason_outside_allowed_session():
    r = sf.check(utc(6, 0))
    assert r["reason"] == "outside_allowed_session"

from datetime import datetime, timezone

from src.app.config_loader import get_config
from src.core.time_filter.session_filter import SessionFilter


def test_session_filter_london_allowed_and_closed_and_reasons() -> None:
    config = get_config()
    flt = SessionFilter(config)

    # 1. SEOUL 포함, 평일 01:00 UTC -> allowed=True, primary_session="SEOUL"
    dt_weekday_seoul = datetime(2024, 1, 2, 1, 0, tzinfo=timezone.utc)
    res_weekday_seoul = flt.evaluate(dt_weekday_seoul)
    assert res_weekday_seoul.allowed is True
    assert res_weekday_seoul.primary_session == "SEOUL"
    assert "SEOUL" in res_weekday_seoul.active_sessions

    # 2. SEOUL 포함, 토요일 01:00 UTC -> allowed=True, primary_session="SEOUL"
    dt_sat_seoul = datetime(2024, 1, 6, 1, 0, tzinfo=timezone.utc)
    res_sat_seoul = flt.evaluate(dt_sat_seoul)
    assert res_sat_seoul.allowed is True
    assert res_sat_seoul.primary_session == "SEOUL"
    assert "SEOUL" in res_sat_seoul.active_sessions

    # config trade_sessions에 LONDON 포함이라는 전제 하에,
    # 평일 런던 시간은 allowed=True
    dt_london = datetime(2024, 1, 2, 9, 0, tzinfo=timezone.utc)
    res_london = flt.evaluate(dt_london)
    assert res_london.allowed is True
    assert res_london.primary_session == "LONDON"
    assert "LONDON" in res_london.active_sessions
    assert res_london.reason == "allowed_session"

    # 3. 평일 06:00 UTC -> CLOSED + outside_allowed_session
    dt_weekday_after_seoul = datetime(2024, 1, 2, 6, 0, tzinfo=timezone.utc)
    res_weekday_after_seoul = flt.evaluate(dt_weekday_after_seoul)
    assert res_weekday_after_seoul.allowed is False
    assert res_weekday_after_seoul.primary_session == "CLOSED"
    assert res_weekday_after_seoul.reason == "outside_allowed_session"

    # 4. 토요일 06:00 UTC -> CLOSED + outside_allowed_session
    dt_sat_after_seoul = datetime(2024, 1, 6, 6, 0, tzinfo=timezone.utc)
    res_sat_after_seoul = flt.evaluate(dt_sat_after_seoul)
    assert res_sat_after_seoul.allowed is False
    assert res_sat_after_seoul.primary_session == "CLOSED"
    assert res_sat_after_seoul.reason == "outside_allowed_session"

    # 5. 평일 14:00 UTC -> allowed=True, primary_session="OVERLAP"
    dt_weekday_overlap = datetime(2024, 1, 2, 14, 0, tzinfo=timezone.utc)
    res_weekday_overlap = flt.evaluate(dt_weekday_overlap)
    assert res_weekday_overlap.allowed is True
    assert res_weekday_overlap.primary_session == "OVERLAP"

