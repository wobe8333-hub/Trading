from src.core.execution_cost_guard.slippage_predictor import SlippagePredictor

PRED = SlippagePredictor()


def test_slippage_positive():
    result = PRED.predict(175.0, {"orderbook_depth_usd": 500_000.0}, "RANGE")
    assert result >= 0.0


def test_slippage_capped_at_20bps():
    # 아주 큰 주문 → 20bps 캡
    result = PRED.predict(10_000_000.0, {"orderbook_depth_usd": 1.0}, "EXPANSION")
    assert result == 20.0


def test_expansion_higher_than_range():
    # EXPANSION은 RANGE보다 slippage 높아야 함
    depth = {"orderbook_depth_usd": 1_000_000.0}
    exp   = PRED.predict(10_000.0, depth, "EXPANSION")
    rng   = PRED.predict(10_000.0, depth, "RANGE")
    assert exp >= rng


def test_zero_depth_returns_max():
    result = PRED.predict(175.0, {"orderbook_depth_usd": 0.0}, "RANGE")
    assert result == 20.0


def test_no_depth_key_returns_max():
    result = PRED.predict(175.0, {}, "RANGE")
    assert result == 20.0


def test_formula_correctness():
    # order=1000, depth=100_000, regime=RANGE(factor=1.0)
    # slippage = (1000/100000)*100*1.0 = 1.0bps
    result = PRED.predict(1_000.0, {"orderbook_depth_usd": 100_000.0}, "RANGE")
    assert abs(result - 1.0) < 1e-4


def test_no_exception_on_bad_state():
    result = PRED.predict(100.0, {"orderbook_depth_usd": "bad"}, "TREND_UP")
    assert result == 20.0

