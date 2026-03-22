from src.core.execution_cost_guard.cost_calculator import CostCalculator

CALC = CostCalculator()

_REQUIRED_KEYS = [
    "spread_cost_bps", "slippage_bps", "fee_bps",
    "total_cost_bps", "maker_fee_bps", "taker_fee_bps",
]


def _state(spread=2.0, depth=500_000.0):
    return {"spread_bps": spread, "orderbook_depth_usd": depth}


# ── 반환 키 구조 ──────────────────────────────────────────────

def test_returns_required_keys():
    result = CALC.compute_total_cost_bps("BTCUSDT", "LIMIT", 175.0, {}, "RANGE")
    for k in _REQUIRED_KEYS:
        assert k in result


# ── fee_bps 검증 ─────────────────────────────────────────────

def test_limit_order_fee_is_4bps():
    result = CALC.compute_total_cost_bps("BTCUSDT", "LIMIT", 175.0, {}, "RANGE")
    assert result["fee_bps"] == 4.0


def test_market_order_fee_is_11bps():
    result = CALC.compute_total_cost_bps("BTCUSDT", "MARKET", 175.0, {}, "RANGE")
    assert result["fee_bps"] == 11.0


# ── spread_cost_bps = spread_bps * 0.5 ───────────────────────

def test_spread_cost_is_half_of_spread():
    result = CALC.compute_total_cost_bps(
        "BTCUSDT", "LIMIT", 175.0, _state(spread=4.0), "RANGE"
    )
    assert abs(result["spread_cost_bps"] - 2.0) < 1e-6


# ── total_cost_bps = spread + slippage + fee ─────────────────

def test_total_cost_is_sum_of_components():
    result = CALC.compute_total_cost_bps(
        "BTCUSDT", "LIMIT", 175.0, _state(spread=2.0, depth=500_000.0), "RANGE"
    )
    expected = result["spread_cost_bps"] + result["slippage_bps"] + result["fee_bps"]
    assert abs(result["total_cost_bps"] - expected) < 1e-4


# ── is_cost_acceptable ────────────────────────────────────────

def test_cost_acceptable_when_within_20pct():
    # total=5bps, tp1=100bps → 5/100=5% < 20% → True
    assert CostCalculator.is_cost_acceptable(5.0, 100.0) is True


def test_cost_blocked_when_exceed_20pct():
    # total=25bps, tp1=100bps → 25/100=25% > 20% → False
    assert CostCalculator.is_cost_acceptable(25.0, 100.0) is False


def test_cost_blocked_when_tp1_zero():
    assert CostCalculator.is_cost_acceptable(5.0, 0.0) is False


def test_cost_boundary_exactly_20pct():
    # total=20bps, tp1=100bps → 20% = 20% → True (경계 포함)
    assert CostCalculator.is_cost_acceptable(20.0, 100.0) is True


# ── maker_fee_bps / taker_fee_bps 참고값 ──────────────────────

def test_fee_reference_values():
    result = CALC.compute_total_cost_bps("BTCUSDT", "LIMIT", 100.0, {}, "RANGE")
    assert result["maker_fee_bps"] == 0.8
    assert result["taker_fee_bps"] == 2.2


# ── 예외 안전성 ─────────────────────────────────────────────

def test_no_exception_on_empty_state():
    result = CALC.compute_total_cost_bps("BTCUSDT", "LIMIT", 0.0, {}, "RANGE")
    assert "total_cost_bps" in result


def test_no_exception_on_bad_state():
    result = CALC.compute_total_cost_bps(
        "BTCUSDT", "LIMIT", 100.0, {"spread_bps": "bad"}, "RANGE"
    )
    assert "total_cost_bps" in result

