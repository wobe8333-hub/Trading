from src.execution.order_router import OrderRouter

ROUTER = OrderRouter(paper_mode=True)


def _state(spread=2.0, depth=500_000.0):
    return {"spread_bps": spread, "orderbook_depth_usd": depth}


def test_hold_on_wide_spread():
    assert ROUTER.decide_order_type("BTCUSDT", _state(spread=7.0)) == "HOLD"


def test_hold_on_low_depth():
    assert ROUTER.decide_order_type("BTCUSDT", _state(depth=10_000.0)) == "HOLD"


def test_market_on_tight_spread():
    assert ROUTER.decide_order_type("BTCUSDT", _state(spread=1.0)) == "MARKET"


def test_limit_on_mid_spread():
    assert ROUTER.decide_order_type("BTCUSDT", _state(spread=4.0)) == "LIMIT"


def test_boundary_spread_6():
    result = ROUTER.decide_order_type("BTCUSDT", _state(spread=6.0, depth=500_000.0))
    assert result in ("MARKET", "LIMIT")


def test_boundary_spread_3():
    assert ROUTER.decide_order_type("BTCUSDT", _state(spread=3.0)) == "LIMIT"


def test_paper_order_returns_dict():
    result = ROUTER.place_order("BTCUSDT", "Buy", 1.0, 43000.0, "LIMIT")
    assert isinstance(result, dict)


def test_paper_order_has_filled_price():
    result = ROUTER.place_order("BTCUSDT", "Buy", 1.0, 43000.0, "LIMIT")
    assert "filled_price" in result
    assert result["filled_price"] > 0


def test_paper_order_status_filled():
    result = ROUTER.place_order("BTCUSDT", "Sell", 0.5, 43000.0, "MARKET")
    assert result.get("status") == "Filled"


def test_paper_mode_flag():
    result = ROUTER.place_order("BTCUSDT", "Buy", 1.0, 43000.0, "LIMIT")
    assert result.get("paper_mode") is True
