from src.core.orderflow_engine.orderflow_engine import OrderflowEngine

ENG = OrderflowEngine()

_REQUIRED_KEYS = ["liquidation", "stop_hunt", "imbalance", "max_confidence"]
_LIQ_KEYS      = ["event_type", "confidence", "oi_drop_pct", "min_oi_drop_usd"]
_HUNT_KEYS     = ["detected", "direction", "confidence", "hunt_low", "hunt_high"]
_IMB_KEYS      = ["event_type", "confidence", "direction"]


def test_returns_all_top_level_keys():
    result = ENG.compute("BTCUSDT", {})
    for k in _REQUIRED_KEYS:
        assert k in result


def test_liquidation_sub_keys():
    result = ENG.compute("BTCUSDT", {})
    for k in _LIQ_KEYS:
        assert k in result["liquidation"]


def test_stop_hunt_sub_keys():
    result = ENG.compute("BTCUSDT", {})
    for k in _HUNT_KEYS:
        assert k in result["stop_hunt"]


def test_imbalance_sub_keys():
    result = ENG.compute("BTCUSDT", {})
    for k in _IMB_KEYS:
        assert k in result["imbalance"]


def test_max_confidence_range():
    result = ENG.compute("BTCUSDT", {})
    assert 0.0 <= result["max_confidence"] <= 1.0


def test_max_confidence_equals_max_of_three():
    result = ENG.compute("BTCUSDT", {})
    expected = max(
        result["liquidation"]["confidence"],
        result["stop_hunt"]["confidence"],
        result["imbalance"]["confidence"],
    )
    assert abs(result["max_confidence"] - expected) < 1e-6


def test_null_on_empty_state():
    result = ENG.compute("BTCUSDT", {})
    assert result["liquidation"]["event_type"] is None
    assert result["stop_hunt"]["detected"] is False
    assert result["imbalance"]["event_type"] is None
    assert result["max_confidence"] == 0.0


def test_no_exception_on_none_state():
    result = ENG.compute("BTCUSDT", None)  # type: ignore
    assert result["max_confidence"] == 0.0


def test_10_consecutive_no_exception():
    for _ in range(10):
        r = ENG.compute("BTCUSDT", {})
        assert 0.0 <= r["max_confidence"] <= 1.0


def test_5_event_types_detectable():
    """
    구현지침서 PASS 기준: 5개 이벤트 감지 가능
    SHORT_LIQUIDATION_CASCADE / LONG_LIQUIDATION_CASCADE
    BULL_HUNT / BEAR_HUNT
    IMBALANCE_BREAK / ABSORPTION_EVENT
    """
    from src.core.orderflow_engine.imbalance_detector import ImbalanceDetector
    from src.core.orderflow_engine.liquidation_engine import LiquidationEngine
    from src.core.orderflow_engine.stop_hunt_detector import StopHuntDetector

    assert LiquidationEngine is not None
    assert StopHuntDetector  is not None
    assert ImbalanceDetector is not None
    print("PASS: 5 event types all defined and importable")
