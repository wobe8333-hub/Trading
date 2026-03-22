from src.core.macro_filter.macro_features import MacroFeatureCalculator

CALC = MacroFeatureCalculator()

_REQUIRED_KEYS = [
    "ema20", "ema50", "ema200", "vwap", "atr_14",
    "atr_expansion", "oi_change_pct", "funding_bias",
    "volume_spike", "price_vs_vwap", "ema_alignment",
]


def _make_klines(n: int, base_close: float = 100.0) -> list:
    """단조 상승하는 테스트용 klines 생성."""
    return [
        {
            "timestamp": i,
            "open":   base_close + i * 0.1,
            "high":   base_close + i * 0.1 + 0.5,
            "low":    base_close + i * 0.1 - 0.3,
            "close":  base_close + i * 0.1,
            "volume": 1000.0 + i,
        }
        for i in range(n)
    ]


def _make_state(**overrides) -> dict:
    base = {
        "klines_3m":      _make_klines(60),
        "last_price":     106.0,
        "open_interest":  5000.0,
        "oi_prev_5m":     4900.0,
        "funding_rate":   0.0001,
    }
    base.update(overrides)
    return base


def test_returns_all_required_keys():
    result = CALC.compute(_make_state())
    for key in _REQUIRED_KEYS:
        assert key in result, f"missing key: {key}"


def test_volume_spike_is_bool():
    result = CALC.compute(_make_state())
    assert isinstance(result["volume_spike"], bool)


def test_price_vs_vwap_valid_value():
    result = CALC.compute(_make_state())
    assert result["price_vs_vwap"] in ("ABOVE", "BELOW", "NEAR")


def test_ema_alignment_valid_value():
    result = CALC.compute(_make_state())
    assert result["ema_alignment"] in ("BULL", "BEAR", "NEUTRAL")


def test_bull_alignment_on_rising_prices():
    klines = _make_klines(100, base_close=100.0)
    result = CALC.compute({"klines_3m": klines, "last_price": 110.0,
                            "open_interest": 1.0, "oi_prev_5m": 1.0, "funding_rate": 0.0})
    assert result["ema_alignment"] == "BULL"


def test_bear_alignment_on_falling_prices():
    klines = [
        {"timestamp": i, "open": 200 - i*0.1, "high": 200 - i*0.1 + 0.3,
         "low": 200 - i*0.1 - 0.3, "close": 200 - i*0.1, "volume": 1000.0}
        for i in range(100)
    ]
    result = CALC.compute({"klines_3m": klines, "last_price": 190.0,
                            "open_interest": 1.0, "oi_prev_5m": 1.0, "funding_rate": 0.0})
    assert result["ema_alignment"] == "BEAR"


def test_oi_change_positive():
    result = CALC.compute(_make_state(open_interest=5100.0, oi_prev_5m=5000.0))
    assert result["oi_change_pct"] > 0


def test_oi_change_negative():
    result = CALC.compute(_make_state(open_interest=4500.0, oi_prev_5m=5000.0))
    assert result["oi_change_pct"] < 0


def test_oi_change_zero_when_equal():
    result = CALC.compute(_make_state(open_interest=5000.0, oi_prev_5m=5000.0))
    assert result["oi_change_pct"] == 0.0


def test_price_above_vwap():
    klines = _make_klines(50, base_close=100.0)
    result = CALC.compute({"klines_3m": klines, "last_price": 200.0,
                            "open_interest": 1.0, "oi_prev_5m": 1.0, "funding_rate": 0.0})
    assert result["price_vs_vwap"] == "ABOVE"


def test_price_below_vwap():
    klines = _make_klines(50, base_close=100.0)
    result = CALC.compute({"klines_3m": klines, "last_price": 1.0,
                            "open_interest": 1.0, "oi_prev_5m": 1.0, "funding_rate": 0.0})
    assert result["price_vs_vwap"] == "BELOW"


def test_atr_expansion_finite_positive():
    result = CALC.compute(_make_state())
    assert result["atr_expansion"] > 0
    assert result["atr_expansion"] < 100


def test_empty_state_returns_default():
    result = CALC.compute({})
    for key in _REQUIRED_KEYS:
        assert key in result


def test_none_values_no_exception():
    result = CALC.compute({
        "klines_3m": None,
        "last_price": None,
        "open_interest": None,
        "oi_prev_5m": None,
        "funding_rate": None,
    })
    for key in _REQUIRED_KEYS:
        assert key in result


def test_volume_spike_detected():
    klines = _make_klines(25, base_close=100.0)
    klines[-1]["volume"] = 100_000.0
    result = CALC.compute({
        "klines_3m": klines, "last_price": 102.0,
        "open_interest": 1.0, "oi_prev_5m": 1.0, "funding_rate": 0.0
    })
    assert result["volume_spike"] is True
