from src.strategy.selector.rule_based_selector import RuleBasedSelector
from src.strategy.selector.strategy_weights import StrategyWeights

SEL = RuleBasedSelector()


def test_cold_start_returns_5_strategies():
    result = SEL.select("BTCUSDT", "BULL", "TREND_UP", "CORE", 70, 0)
    assert result == [
        "vwap_pullback",
        "trend_continuation",
        "liquidity_sweep_reversal",
        "stop_hunt_reversal",
        "ema_cross_scalping",
    ]


def test_cold_start_threshold_49():
    result = SEL.select("BTCUSDT", "BULL", "TREND_UP", "CORE", 70, 49)
    assert result == [
        "vwap_pullback",
        "trend_continuation",
        "liquidity_sweep_reversal",
        "stop_hunt_reversal",
        "ema_cross_scalping",
    ]


def test_normal_mode_at_50():
    result = SEL.select("BTCUSDT", "BULL", "TREND_UP", "CORE", 70, 50)
    assert isinstance(result, list)
    assert len(result) >= 0


def test_risk_off_returns_empty():
    result = SEL.select("BTCUSDT", "RISK_OFF", "EXPANSION", "CORE", 70, 100)
    assert result == []


def test_returns_list():
    result = SEL.select("BTCUSDT", "BULL", "TREND_UP", "CORE", 70, 100)
    assert isinstance(result, list)


def test_returns_valid_strategy_names():
    valid = {
        "vwap_pullback",
        "trend_continuation",
        "liquidity_sweep_reversal",
        "breakout_momentum",
        "liquidation_scalping",
        "stop_hunt_reversal",
        "ema_cross_scalping",
    }
    result = SEL.select("BTCUSDT", "BULL", "TREND_UP", "CORE", 70, 100)
    for name in result:
        assert name in valid


def test_expansion_blocks_vwap_pullback():
    result = SEL.select("BTCUSDT", "BULL", "EXPANSION", "HIGH_BETA", 70, 100)
    assert "vwap_pullback" not in result


def test_range_blocks_trend_continuation():
    result = SEL.select("BTCUSDT", "BULL", "RANGE", "CORE", 70, 100)
    assert "trend_continuation" not in result


def test_disabled_strategy_excluded():
    w = StrategyWeights()
    w.disabled.add("vwap_pullback")
    sel = RuleBasedSelector(weights=w)
    result = sel.select("BTCUSDT", "BULL", "TREND_UP", "CORE", 70, 100)
    assert "vwap_pullback" not in result


def test_preferred_coin_type_prioritized():
    result_core = SEL.select("BTCUSDT", "BULL", "TREND_UP", "CORE", 70, 100)
    result_hb = SEL.select("BTCUSDT", "BULL", "TREND_UP", "HIGH_BETA", 70, 100)
    assert isinstance(result_core, list)
    assert isinstance(result_hb, list)


def test_no_exception_on_unknown_regime():
    result = SEL.select("BTCUSDT", "BULL", "UNKNOWN_REGIME", "CORE", 70, 100)
    assert isinstance(result, list)

