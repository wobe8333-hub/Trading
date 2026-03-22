from src.execution.spread_guard import SpreadGuard
from src.execution.orderbook_guard import OrderbookGuard
from src.execution.slippage_guard import SlippageGuard

SG = SpreadGuard()
OBG = OrderbookGuard()
SLG = SlippageGuard()


def test_spread_ok_normal():
    ok, reason = SG.is_spread_ok("BTCUSDT", {"spread_bps": 2.0})
    assert ok is True


def test_spread_blocked_wide():
    ok, reason = SG.is_spread_ok("BTCUSDT", {"spread_bps": 10.0})
    assert ok is False
    assert "SPREAD" in reason


def test_spread_boundary_6():
    ok, _ = SG.is_spread_ok("BTCUSDT", {"spread_bps": 6.0})
    assert ok is True


def test_spread_no_exception_empty():
    ok, _ = SG.is_spread_ok("BTCUSDT", {})
    assert isinstance(ok, bool)


def test_depth_ok_normal():
    ok, reason = OBG.is_depth_ok("BTCUSDT", {"orderbook_depth_usd": 500_000.0})
    assert ok is True


def test_depth_blocked_low():
    ok, reason = OBG.is_depth_ok("BTCUSDT", {"orderbook_depth_usd": 1_000.0})
    assert ok is False
    assert "DEPTH" in reason


def test_depth_boundary_50k():
    ok, _ = OBG.is_depth_ok("BTCUSDT", {"orderbook_depth_usd": 50_000.0})
    assert ok is True


def test_depth_no_exception_empty():
    ok, _ = OBG.is_depth_ok("BTCUSDT", {})
    assert isinstance(ok, bool)


def test_slippage_ok_normal():
    ok, reason = SLG.is_slippage_ok(
        "BTCUSDT", 175.0,
        {"orderbook_depth_usd": 1_000_000.0}, "RANGE"
    )
    assert ok is True


def test_slippage_blocked_high():
    ok, reason = SLG.is_slippage_ok(
        "BTCUSDT", 100_000_000.0,
        {"orderbook_depth_usd": 1.0}, "EXPANSION"
    )
    assert ok is False
    assert "SLIPPAGE" in reason


def test_slippage_no_exception_empty():
    ok, _ = SLG.is_slippage_ok("BTCUSDT", 175.0, {}, "RANGE")
    assert isinstance(ok, bool)
