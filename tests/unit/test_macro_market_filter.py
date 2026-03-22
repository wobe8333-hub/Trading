from src.core.macro_filter.macro_market_filter import MacroMarketFilter

FILTER = MacroMarketFilter()

_VALID_STATES = {"BULL", "BEAR", "NEUTRAL", "RISK_OFF"}


def _make_klines(n: int, close_start: float = 100.0, direction: str = "up") -> list:
    klines = []
    for i in range(n):
        c = close_start + (i * 0.5 if direction == "up" else -i * 0.5)
        klines.append({
            "timestamp": i,
            "open":   c - 0.1, "high": c + 0.3,
            "low":    c - 0.3, "close": c,
            "volume": 500.0,
        })
    return klines


def _bull_state() -> dict:
    klines = _make_klines(100, close_start=100.0, direction="up")
    return {
        "klines_3m":     klines,
        "last_price":    150.0,
        "open_interest": 5100.0,
        "oi_prev_5m":    5000.0,
        "funding_rate":  0.0001,
    }


def _bear_state() -> dict:
    klines = _make_klines(100, close_start=200.0, direction="down")
    return {
        "klines_3m":     klines,
        "last_price":    1.0,
        "open_interest": 4900.0,
        "oi_prev_5m":    5000.0,
        "funding_rate":  -0.0001,
    }


def _risk_off_state() -> dict:
    base = _make_klines(30, close_start=100.0)
    for k in base:
        k["high"]   = k["close"] + 0.1
        k["low"]    = k["close"] - 0.1
        k["volume"] = 100.0
    base[-1]["high"]   = base[-1]["close"] + 50.0
    base[-1]["low"]    = base[-1]["close"] - 50.0
    base[-1]["volume"] = 100_000.0
    return {
        "klines_3m":     base,
        "last_price":    base[-1]["close"],
        "open_interest": 4400.0,
        "oi_prev_5m":    5000.0,
        "funding_rate":  0.002,
    }


def test_get_state_returns_valid_state():
    result = FILTER.get_state({})
    assert result in _VALID_STATES


def test_get_state_always_string():
    for state in (_bull_state(), _bear_state(), {}):
        result = FILTER.get_state(state)
        assert isinstance(result, str)
        assert result in _VALID_STATES


def test_bull_conditions():
    result = FILTER.get_state(_bull_state())
    assert result == "BULL"


def test_bear_conditions():
    result = FILTER.get_state(_bear_state())
    assert result == "BEAR"


def test_risk_off_priority():
    result = FILTER.get_state(_risk_off_state())
    assert result == "RISK_OFF"


def test_neutral_on_empty_data():
    result = FILTER.get_state({})
    assert result == "NEUTRAL"


def test_neutral_on_mixed_signals():
    klines = _make_klines(100, direction="up")
    state = {
        "klines_3m":     klines,
        "last_price":    150.0,
        "open_interest": 4900.0,
        "oi_prev_5m":    5000.0,
        "funding_rate":  0.0,
    }
    result = FILTER.get_state(state)
    assert result in _VALID_STATES


def test_risk_off_overrides_bull_signal():
    state = _risk_off_state()
    result = FILTER.get_state(state)
    assert result == "RISK_OFF"


def test_get_features_returns_dict():
    feat = FILTER.get_features(_bull_state())
    assert isinstance(feat, dict)
    for key in ["ema20", "ema50", "atr_expansion",
                "oi_change_pct", "volume_spike",
                "price_vs_vwap", "ema_alignment"]:
        assert key in feat


def test_no_exception_on_none_state():
    result = FILTER.get_state(None)  # type: ignore
    assert result in _VALID_STATES


def test_no_exception_on_bad_types():
    result = FILTER.get_state({"klines_3m": "bad", "last_price": "abc"})
    assert result in _VALID_STATES


def test_10_consecutive_no_exception():
    for _ in range(10):
        result = FILTER.get_state(_bull_state())
        assert result in _VALID_STATES
