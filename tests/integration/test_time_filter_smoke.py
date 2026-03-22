from datetime import datetime, timedelta, timezone

from src.core.time_filter.session_filter import SessionFilter


def test_full_24h_smoke() -> None:
    """24시간 × 15분 간격 96회 연속 실행 — 예외 없음, 구조 유지."""
    sf = SessionFilter()
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for minute_offset in range(0, 1440, 15):
        dt = base + timedelta(minutes=minute_offset)
        r = sf.check(dt)
        assert "allowed" in r
        assert r["primary_session"] in ["SEOUL", "LONDON", "NY", "OVERLAP", "CLOSED"]
        assert isinstance(r["active_sessions"], list)
        assert r["reason"] in ["allowed_session", "outside_allowed_session"]


def test_full_week_smoke() -> None:
    """7일 연속 실행 — 예외 없음."""
    sf = SessionFilter()
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for day in range(7):
        for hour in range(24):
            dt = base + timedelta(days=day, hours=hour)
            r = sf.check(dt)
            assert r["allowed"] in [True, False]


def test_config_based_filter_smoke() -> None:
    """config 주입 버전 — 동일 결과."""
    from src.app.config_loader import get_config

    cfg = get_config()
    sf = SessionFilter(cfg)

    dt_seoul = datetime(2024, 1, 2, 1, 0, tzinfo=timezone.utc)
    r = sf.check(dt_seoul)
    assert r["allowed"] is True
    assert r["primary_session"] == "SEOUL"

    dt_closed = datetime(2024, 1, 2, 6, 0, tzinfo=timezone.utc)
    r2 = sf.check(dt_closed)
    assert r2["allowed"] is False
    assert r2["primary_session"] == "CLOSED"


def test_96_consecutive_no_exception() -> None:
    """96회 연속 실행 중 예외 없음 확인."""
    sf = SessionFilter()
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    count = 0
    for minute_offset in range(0, 1440, 15):
        sf.check(base + timedelta(minutes=minute_offset))
        count += 1
    assert count == 96


def test_7_days_no_exception() -> None:
    """7일 연속 실행 중 예외 없음 확인."""
    sf = SessionFilter()
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for day in range(7):
        for hour in range(24):
            sf.check(base + timedelta(days=day, hours=hour))

from datetime import datetime, timezone

from src.app.config_loader import get_config
from src.core.time_filter.session_filter import SessionFilter


def test_time_filter_smoke() -> None:
    config = get_config()
    flt = SessionFilter(config)

    # 1. load_config 후 SessionFilter 초기화 가능 (위에서 이미 수행)
    assert "SEOUL" in config.trade_sessions

    # 2. 평일 01:00 UTC -> primary_session == "SEOUL"
    dt_weekday_seoul = datetime(2024, 1, 2, 1, 0, tzinfo=timezone.utc)
    res_weekday_seoul = flt.evaluate(dt_weekday_seoul)
    assert res_weekday_seoul.primary_session == "SEOUL"

    # 3. 토요일 01:00 UTC -> primary_session == "SEOUL"
    dt_sat_seoul = datetime(2024, 1, 6, 1, 0, tzinfo=timezone.utc)
    res_sat_seoul = flt.evaluate(dt_sat_seoul)
    assert res_sat_seoul.primary_session == "SEOUL"

    # 4. 평일 14:00 UTC -> primary_session == "OVERLAP"
    dt_weekday_overlap = datetime(2024, 1, 2, 14, 0, tzinfo=timezone.utc)
    res_weekday_overlap = flt.evaluate(dt_weekday_overlap)
    assert res_weekday_overlap.primary_session == "OVERLAP"

    # 5. 반환 구조 유지 확인
    for res in (res_weekday_seoul, res_sat_seoul, res_weekday_overlap):
        assert isinstance(res.allowed, bool)
        assert isinstance(res.primary_session, str)
        assert isinstance(res.active_sessions, list)
        assert isinstance(res.reason, str)
        assert isinstance(res.checked_ts_utc, str)
        assert "primary_session" in res.__dict__
        assert "active_sessions" in res.__dict__
        assert "allowed" in res.__dict__

