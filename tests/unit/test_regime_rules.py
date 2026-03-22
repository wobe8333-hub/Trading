from src.core.regime_engine.regime_rules import (
    REGIME_RULES,
    REGIME_PRIORITY,
    VALID_REGIMES,
)


def test_regime_rules_has_4_entries():
    assert len(REGIME_RULES) == 4


def test_expansion_keys_present():
    r = REGIME_RULES["EXPANSION"]
    assert "atr_expansion_min"  in r
    assert "volume_spike_ratio" in r


def test_trend_up_keys_present():
    r = REGIME_RULES["TREND_UP"]
    assert "ema20_above_ema50" in r
    assert "price_above_vwap"  in r
    assert "hh_hl_min_count"   in r


def test_trend_down_keys_present():
    r = REGIME_RULES["TREND_DOWN"]
    assert "ema20_below_ema50" in r
    assert "price_below_vwap"  in r
    assert "ll_lh_min_count"   in r


def test_range_keys_present():
    r = REGIME_RULES["RANGE"]
    assert "ema_diff_max_pct"  in r
    assert "atr_expansion_max" in r


def test_regime_priority_order():
    """EXPANSION이 반드시 첫 번째여야 한다."""
    assert REGIME_PRIORITY[0] == "EXPANSION"
    assert len(REGIME_PRIORITY) == 4


def test_valid_regimes_set():
    assert VALID_REGIMES == {"EXPANSION", "TREND_UP", "TREND_DOWN", "RANGE"}


def test_atr_expansion_min_value():
    """초기값 검증: ATR expansion 기준 1.8."""
    assert REGIME_RULES["EXPANSION"]["atr_expansion_min"] == 1.8


def test_volume_spike_ratio_value():
    """초기값 검증: 거래량 비율 기준 2.0."""
    assert REGIME_RULES["EXPANSION"]["volume_spike_ratio"] == 2.0


def test_hh_hl_min_count_value():
    """초기값 검증: HH+HL 최소 횟수 2."""
    assert REGIME_RULES["TREND_UP"]["hh_hl_min_count"] == 2
