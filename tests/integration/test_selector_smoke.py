from src.strategy.selector.ml_selector import MLStrategySelector
from src.strategy.selector.rule_based_selector import RuleBasedSelector
from src.strategy.selector.strategy_feedback import StrategyFeedback
from src.strategy.selector.strategy_weights import StrategyWeights

_VALID_STRATEGIES = {
    "vwap_pullback",
    "trend_continuation",
    "liquidity_sweep_reversal",
    "breakout_momentum",
    "liquidation_scalping",
    "stop_hunt_reversal",
    "ema_cross_scalping",
}


def test_pass_criteria():
    """
    구현지침서 공식 PASS 기준:
    sel.select('BTCUSDT', 'BULL', 'TREND_UP', 'CORE', 70, 100)
    """
    sel = RuleBasedSelector()
    result = sel.select("BTCUSDT", "BULL", "TREND_UP", "CORE", 70, 100)
    assert isinstance(result, list)
    for name in result:
        assert name in _VALID_STRATEGIES


def test_all_macro_states():
    sel = RuleBasedSelector()
    for macro in ["BULL", "BEAR", "NEUTRAL", "RISK_OFF"]:
        for regime in ["TREND_UP", "TREND_DOWN", "RANGE", "EXPANSION"]:
            result = sel.select("BTCUSDT", macro, regime, "CORE", 70, 100)
            assert isinstance(result, list)
            if macro == "RISK_OFF":
                assert result == []


def test_feedback_weight_integration():
    w = StrategyWeights()
    fb = StrategyFeedback(w)
    sel = RuleBasedSelector(weights=w)

    for _ in range(20):
        fb.record("vwap_pullback", "BTCUSDT", "TREND_UP", 5.0, 1.5)

    fb.trigger_weight_update()

    result = sel.select("BTCUSDT", "BULL", "TREND_UP", "CORE", 70, 100)
    assert "vwap_pullback" in result


def test_cold_start_integration():
    sel = RuleBasedSelector()
    result = sel.select("BTCUSDT", "BULL", "TREND_UP", "CORE", 70, 0)
    assert result == [
        "vwap_pullback",
        "trend_continuation",
        "liquidity_sweep_reversal",
        "stop_hunt_reversal",
        "ema_cross_scalping",
    ]


def test_ml_selector_passthrough():
    ml = MLStrategySelector()
    sel = RuleBasedSelector(ml_selector=ml)
    assert ml.is_active() is False
    result = sel.select("BTCUSDT", "BULL", "TREND_UP", "CORE", 70, 100)
    assert isinstance(result, list)

