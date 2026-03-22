from src.execution.execution_engine import ExecutionEngine

_REQUIRED_KEYS = [
    "order_id", "symbol", "direction", "qty",
    "entry_price", "filled_price", "order_type",
    "fee_usd", "sl_registered", "timestamp",
]


def _eng():
    return ExecutionEngine(paper_mode=True)


def _good_state():
    return {"spread_bps": 2.0, "orderbook_depth_usd": 10_000_000.0}


def test_pass_criteria():
    e = _eng()
    result = e.execute(
        symbol="BTCUSDT", direction="LONG",
        position_scale=0.7, position_size_contracts=11.2,
        entry_price=43000.0, stop_price=42500.0,
        tp1_price=43600.0, tp2_price=44000.0,
        tp1_ratio=0.5, regime="TREND_UP",
        market_state=_good_state(),
    )
    assert not result["blocked"]
    assert result["sl_registered"] is True
    assert result["fee_usd"] > 0


def test_all_required_keys_present():
    e = _eng()
    result = e.execute(
        "BTCUSDT", "LONG", 0.7, 11.2, 43000.0, 42500.0,
        43600.0, 44000.0, 0.5, "TREND_UP", _good_state(),
    )
    for k in _REQUIRED_KEYS:
        assert k in result, f"missing: {k}"


def test_fee_usd_formula_limit():
    e = _eng()
    result = e.execute(
        "BTCUSDT", "LONG", 0.7, 11.2, 43000.0, 42500.0,
        43600.0, 44000.0, 0.5, "TREND_UP",
        {"spread_bps": 4.0, "orderbook_depth_usd": 500_000.0},
    )
    if result["order_type"] == "LIMIT":
        qty_usd = result["qty"] * result["filled_price"]
        expected = round(qty_usd * 0.0002, 6)
        assert abs(result["fee_usd"] - expected) < 1e-3


def test_50_consecutive_no_exception():
    e = _eng()
    for _ in range(50):
        result = e.execute(
            "BTCUSDT", "LONG", 0.7, 5.0, 43000.0, 42500.0,
            43600.0, 44000.0, 0.5, "TREND_UP", _good_state(),
        )
        assert isinstance(result, dict)
        assert "blocked" in result


def test_short_direction_works():
    e = _eng()
    result = e.execute(
        "BTCUSDT", "SHORT", 0.7, 5.0, 43000.0, 43500.0,
        42400.0, 42000.0, 0.5, "TREND_DOWN", _good_state(),
    )
    if not result["blocked"]:
        assert result["direction"] == "SHORT"
