from src.core.orderflow_engine.imbalance_detector import ImbalanceDetector

DET = ImbalanceDetector()


def test_returns_required_keys():
    result = DET.detect("BTCUSDT", {})
    for k in ["event_type", "confidence", "direction"]:
        assert k in result


def test_null_on_empty_state():
    result = DET.detect("BTCUSDT", {})
    assert result["event_type"] is None
    assert result["confidence"] == 0.0
    assert result["direction"] == "NONE"


def test_null_on_normal_ratio():
    result = DET.detect("BTCUSDT", {
        "bid_ask_ratio": 1.2, "price_impulse_atr": 0.1
    })
    assert result["event_type"] is None


def test_imbalance_break_buy():
    result = DET.detect("BTCUSDT", {
        "bid_ask_ratio": 2.5, "price_impulse_atr": 1.0
    })
    assert result["event_type"] == "IMBALANCE_BREAK"
    assert result["direction"] == "BUY"
    assert 0.0 < result["confidence"] <= 1.0


def test_imbalance_break_sell():
    result = DET.detect("BTCUSDT", {
        "bid_ask_ratio": 0.3, "price_impulse_atr": -1.0
    })
    assert result["event_type"] == "IMBALANCE_BREAK"
    assert result["direction"] == "SELL"
    assert 0.0 < result["confidence"] <= 1.0


def test_absorption_event_detected():
    result = DET.detect("BTCUSDT", {
        "ask_depth_change_pct": 0.8,
        "price_impulse_atr":    0.1,
        "bid_ask_ratio":        1.0,
    })
    assert result["event_type"] == "ABSORPTION_EVENT"
    assert result["direction"] == "BUY"
    assert 0.0 < result["confidence"] <= 1.0


def test_confidence_always_0_to_1():
    states = [
        {"bid_ask_ratio": 3.0, "price_impulse_atr": 2.0},
        {"bid_ask_ratio": 0.1, "price_impulse_atr": -2.0},
        {"ask_depth_change_pct": 2.0, "price_impulse_atr": 0.0},
        {},
    ]
    for state in states:
        r = DET.detect("BTCUSDT", state)
        assert 0.0 <= r["confidence"] <= 1.0


def test_no_exception_on_bad_types():
    result = DET.detect("BTCUSDT", {
        "bid_ask_ratio": "bad", "price_impulse_atr": None
    })
    assert result["event_type"] is None
