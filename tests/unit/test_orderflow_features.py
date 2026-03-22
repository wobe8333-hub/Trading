from src.core.orderflow_engine.orderflow_features import OrderflowFeatureCalculator

CALC = OrderflowFeatureCalculator()

_REQUIRED_KEYS = [
    "oi_change_1m_pct", "oi_change_5m_pct", "volume_spike_ratio",
    "price_impulse_atr", "bid_depth_change_pct", "ask_depth_change_pct",
    "trade_velocity", "absorption_signal",
]


def test_returns_all_required_keys():
    result = CALC.compute("BTCUSDT", {})
    for k in _REQUIRED_KEYS:
        assert k in result, f"missing key: {k}"


def test_absorption_signal_is_bool():
    result = CALC.compute("BTCUSDT", {})
    assert isinstance(result["absorption_signal"], bool)


def test_oi_change_positive():
    state = {"open_interest": 5100.0, "oi_prev_5m": 5000.0}
    result = CALC.compute("BTCUSDT", state)
    assert result["oi_change_5m_pct"] > 0
    assert result["oi_change_1m_pct"] > 0


def test_oi_change_negative():
    state = {"open_interest": 4900.0, "oi_prev_5m": 5000.0}
    result = CALC.compute("BTCUSDT", state)
    assert result["oi_change_5m_pct"] < 0


def test_volume_spike_ratio_gt1_on_spike():
    klines = [{"volume": 100.0, "close": 100.0, "open": 100.0,
               "high": 100.5, "low": 99.5, "timestamp": i}
              for i in range(21)]
    klines[-1]["volume"] = 1000.0
    result = CALC.compute("BTCUSDT", {"klines_1m": klines})
    assert result["volume_spike_ratio"] > 1.0


def test_trade_velocity_equals_trade_count():
    trades = [{"price": 1, "size": 1, "side": "Buy", "ts_ms": i}
              for i in range(15)]
    result = CALC.compute("BTCUSDT", {"recent_trades": trades})
    assert result["trade_velocity"] == 15.0


def test_empty_state_no_exception():
    result = CALC.compute("BTCUSDT", {})
    assert result["oi_change_1m_pct"] == 0.0
    assert result["volume_spike_ratio"] == 1.0


def test_none_values_no_exception():
    result = CALC.compute("BTCUSDT", {
        "open_interest": None, "oi_prev_5m": None,
        "klines_1m": None, "klines_3m": None,
    })
    for k in _REQUIRED_KEYS:
        assert k in result
