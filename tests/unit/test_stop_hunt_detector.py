from src.core.orderflow_engine.stop_hunt_detector import StopHuntDetector

DET = StopHuntDetector()


def _make_klines(n=15, close=100.0, vol=500.0):
    return [
        {"timestamp": i, "open": close, "high": close + 0.3,
         "low": close - 0.3, "close": close, "volume": vol}
        for i in range(n)
    ]


def _bull_hunt_state():
    """BULL_HUNT 조건을 만족하는 state 생성."""
    klines = _make_klines(15, close=100.0)
    # 마지막 봉: 지지선 하방 돌파 + 긴 아래꼬리 + 지지선 위 회복 클로즈
    klines[-1]["open"]  = 99.5
    klines[-1]["high"]  = 99.6
    klines[-1]["low"]   = 95.0   # 지지선(99.7) 하방 큰 돌파
    klines[-1]["close"] = 99.8   # 지지선 위 회복
    return {"klines_3m": klines, "last_price": 99.8}


def _features(oi=-0.02, bid=0.1):
    return {
        "oi_change_5m_pct":    oi,
        "bid_depth_change_pct": bid,
    }


def test_returns_required_keys():
    result = DET.detect("BTCUSDT", {}, {})
    for k in ["detected", "direction", "confidence", "hunt_low", "hunt_high"]:
        assert k in result


def test_no_detection_on_empty_state():
    result = DET.detect("BTCUSDT", {}, {})
    assert result["detected"] is False
    assert result["direction"] == "NONE"
    assert result["confidence"] == 0.0


def test_no_detection_on_normal_candles():
    klines = _make_klines(15)
    result = DET.detect("BTCUSDT", {"klines_3m": klines}, {})
    assert result["detected"] is False


def test_bull_hunt_detected():
    result = DET.detect("BTCUSDT", _bull_hunt_state(), _features())
    if result["detected"]:
        assert result["direction"] == "BULL_HUNT"
        assert 0.0 < result["confidence"] <= 1.0
        assert result["hunt_low"] is not None


def test_confidence_always_0_to_1():
    for _ in range(5):
        r = DET.detect("BTCUSDT", _bull_hunt_state(), _features())
        assert 0.0 <= r["confidence"] <= 1.0


def test_confidence_max_1():
    feat = {"oi_change_5m_pct": -0.1, "bid_depth_change_pct": 1.0}
    r = DET.detect("BTCUSDT", _bull_hunt_state(), feat)
    assert r["confidence"] <= 1.0


def test_no_exception_on_none_state():
    result = DET.detect("BTCUSDT", None, {})  # type: ignore
    assert result["detected"] is False


def test_no_exception_on_bad_klines():
    result = DET.detect("BTCUSDT", {"klines_3m": "bad"}, {})
    assert result["detected"] is False
