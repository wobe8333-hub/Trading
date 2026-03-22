from src.execution.execution_engine import ExecutionEngine

_REQUIRED_KEYS = [
    "order_id", "symbol", "direction", "qty",
    "entry_price", "filled_price", "order_type",
    "fee_usd", "sl_registered", "timestamp",
]


def _eng():
    return ExecutionEngine(paper_mode=True)


def _good_state():
    # order_size_usd ≈ 11.2*0.7*43000 — depth가 작으면 SlippagePredictor가 15bps 초과
    return {
        "spread_bps": 2.0,
        "orderbook_depth_usd": 10_000_000.0,
    }


def _call(**kwargs):
    defaults = dict(
        symbol="BTCUSDT", direction="LONG",
        position_scale=0.7, position_size_contracts=11.2,
        entry_price=43000.0, stop_price=42500.0,
        tp1_price=43600.0, tp2_price=44000.0,
        tp1_ratio=0.5, regime="TREND_UP",
        market_state=_good_state(),
    )
    defaults.update(kwargs)
    return _eng().execute(**defaults)


def test_paper_mode_execute_success():
    result = _call()
    assert result["blocked"] is False
    assert result["sl_registered"] is True
    assert result["qty"] > 0


def test_fee_usd_limit_order():
    result = _call(market_state={"spread_bps": 4.0, "orderbook_depth_usd": 500_000.0})
    if result["order_type"] == "LIMIT":
        qty_usd = result["qty"] * result["filled_price"]
        expected = round(qty_usd * 0.0002, 6)
        assert abs(result["fee_usd"] - expected) < 1e-4


def test_fee_usd_market_order():
    result = _call(market_state={"spread_bps": 1.0, "orderbook_depth_usd": 500_000.0})
    if result["order_type"] == "MARKET":
        qty_usd = result["qty"] * result["filled_price"]
        expected = round(qty_usd * 0.00055, 6)
        assert abs(result["fee_usd"] - expected) < 1e-4


def test_returns_required_keys():
    result = _call()
    for k in _REQUIRED_KEYS:
        assert k in result, f"missing key: {k}"


def test_returns_dict():
    result = _call()
    assert isinstance(result, dict)


def test_qty_equals_contracts_times_scale():
    result = _call(position_scale=0.7, position_size_contracts=11.2)
    if not result["blocked"]:
        expected = round(11.2 * 0.7, 3)
        assert abs(result["qty"] - expected) < 0.01


def test_spread_too_wide_blocked():
    result = _call(market_state={"spread_bps": 10.0, "orderbook_depth_usd": 500_000.0})
    assert result["blocked"] is True
    assert "SPREAD" in result.get("reason", "")


def test_depth_too_low_blocked():
    result = _call(market_state={"spread_bps": 2.0, "orderbook_depth_usd": 1_000.0})
    assert result["blocked"] is True
    assert "DEPTH" in result.get("reason", "")


def test_sl_registered_true_in_paper_mode():
    result = _call()
    if not result["blocked"]:
        assert result["sl_registered"] is True


def test_long_direction():
    result = _call(direction="LONG")
    assert result["direction"] == "LONG"


def test_short_direction():
    result = _call(direction="SHORT")
    assert result["direction"] == "SHORT"


def test_no_exception_on_zero_qty():
    result = _call(position_scale=0.0, position_size_contracts=0.0)
    assert isinstance(result, dict)


def test_no_exception_on_empty_state():
    result = _call(market_state={})
    assert isinstance(result, dict)
    assert "blocked" in result
