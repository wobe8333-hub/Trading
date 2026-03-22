from src.core.orderflow_engine.liquidation_engine import LiquidationEngine

ENG = LiquidationEngine()

_NULL = {"event_type": None, "confidence": 0.0,
         "oi_drop_pct": 0.0, "min_oi_drop_usd": 0.0}


def _short_liq_features(oi_drop=-0.05, impulse=-2.5, spike=4.0,
                         oi=10_000_000, absorption=False):
    return {
        "oi_change_1m_pct":   oi_drop,
        "price_impulse_atr":  impulse,
        "volume_spike_ratio": spike,
        "open_interest":      oi,
        "absorption_signal":  absorption,
    }


def test_returns_required_keys_null():
    result = ENG.detect("BTCUSDT", {})
    for k in ["event_type", "confidence", "oi_drop_pct", "min_oi_drop_usd"]:
        assert k in result


def test_no_event_on_empty_features():
    result = ENG.detect("BTCUSDT", {})
    assert result["event_type"] is None
    assert result["confidence"] == 0.0


def test_no_event_on_mild_oi_drop():
    """OI 감소가 threshold 미만 → 미감지."""
    result = ENG.detect("BTCUSDT", _short_liq_features(oi_drop=-0.01))
    assert result["event_type"] is None


def test_short_liquidation_detected():
    result = ENG.detect("BTCUSDT", _short_liq_features())
    assert result["event_type"] == "SHORT_LIQUIDATION_CASCADE"
    assert 0.0 < result["confidence"] <= 1.0


def test_confidence_range():
    result = ENG.detect("BTCUSDT", _short_liq_features())
    assert 0.0 <= result["confidence"] <= 1.0


def test_confidence_increases_with_deep_oi_drop():
    base   = ENG.detect("BTCUSDT", _short_liq_features(oi_drop=-0.04))
    deeper = ENG.detect("BTCUSDT", _short_liq_features(oi_drop=-0.06))
    if deeper["event_type"] and base["event_type"]:
        assert deeper["confidence"] >= base["confidence"]


def test_confidence_increases_with_absorption():
    no_abs = ENG.detect("BTCUSDT", _short_liq_features(absorption=False))
    with_abs = ENG.detect("BTCUSDT", _short_liq_features(absorption=True))
    if no_abs["event_type"] and with_abs["event_type"]:
        assert with_abs["confidence"] >= no_abs["confidence"]


def test_confidence_never_exceeds_1():
    result = ENG.detect("BTCUSDT", _short_liq_features(
        oi_drop=-0.1, spike=10.0, absorption=True, oi=10_000_000
    ))
    assert result["confidence"] <= 1.0


def test_no_exception_on_bad_input():
    result = ENG.detect("BTCUSDT", {"oi_change_1m_pct": "bad"})
    assert result["event_type"] is None
