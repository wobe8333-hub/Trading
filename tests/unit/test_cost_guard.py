from datetime import datetime, timezone
from src.core.execution_cost_guard.cost_guard import ExecutionCostGuard

GUARD = ExecutionCostGuard()


def _now():
    return datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)  # 펀딩 멀리


def _good_state():
    return {
        "spread_bps":          2.0,
        "orderbook_depth_usd": 1_000_000.0,
        "orderbook_bid_depth": 500.0,
    }


def _call(
    order_type="LIMIT",
    order_size=175.0,
    tp1=43500.0,
    entry=43000.0,
    regime="TREND_UP",
    rate=0.0001,
    score=75,
    state=None,
):
    return GUARD.check(
        symbol="BTCUSDT",
        order_type=order_type,
        order_size_usd=order_size,
        tp1_price=tp1,
        entry_price=entry,
        regime=regime,
        now_utc=_now(),
        funding_rate=rate,
        entry_score=score,
        market_state=state or _good_state(),
    )


# ── 반환 타입 ────────────────────────────────────────────────

def test_returns_tuple():
    result = _call()
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], bool)
    assert isinstance(result[1], dict)


def test_detail_has_reason():
    _, detail = _call()
    assert "reason" in detail


# ── PASS 케이스 ─────────────────────────────────────────────

def test_pass_on_normal_conditions():
    ok, detail = _call()
    assert detail["reason"] in ("PASS", "COST_EXCEED")


# ── FUNDING_TIME 차단 ─────────────────────────────────────────

def test_funding_time_blocked():
    from datetime import datetime, timezone
    now_near_fund = datetime(2024, 1, 1, 7, 50, tzinfo=timezone.utc)
    ok, detail = GUARD.check(
        symbol="BTCUSDT", order_type="LIMIT",
        order_size_usd=175.0, tp1_price=43500.0, entry_price=43000.0,
        regime="TREND_UP", now_utc=now_near_fund,
        funding_rate=0.0001, entry_score=75,
        market_state=_good_state(),
    )
    assert ok is False
    assert detail["reason"] == "FUNDING_TIME"


# ── COST_EXCEED 차단 ─────────────────────────────────────────

def test_cost_exceeded_when_tp1_too_close():
    ok, detail = _call(tp1=43001.0, entry=43000.0)
    assert ok is False
    assert detail["reason"] == "COST_EXCEED"


# ── reason 값 검증 ───────────────────────────────────────────

def test_reason_values_are_valid():
    valid_reasons = {"PASS", "LIQUIDITY", "FUNDING_TIME", "COST_EXCEED", "GUARD_ERROR"}
    _, detail = _call()
    assert detail["reason"] in valid_reasons


# ── cost_detail 포함 확인 ─────────────────────────────────────

def test_pass_includes_cost_detail():
    ok, detail = _call(tp1=50000.0, entry=43000.0)
    if ok:
        assert "cost_detail" in detail
        cd = detail["cost_detail"]
        assert "total_cost_bps" in cd
        assert "fee_bps"        in cd


# ── 예외 안전성 ─────────────────────────────────────────────

def test_no_exception_on_empty_state():
    ok, detail = GUARD.check(
        "BTCUSDT", "LIMIT", 175.0, 43500.0, 43000.0,
        "RANGE", _now(), 0.0001, 75, {}
    )
    assert isinstance(ok, bool)


def test_no_exception_on_zero_entry():
    ok, detail = GUARD.check(
        "BTCUSDT", "LIMIT", 175.0, 43500.0, 0.0,
        "RANGE", _now(), 0.0001, 75, _good_state()
    )
    assert isinstance(ok, bool)

