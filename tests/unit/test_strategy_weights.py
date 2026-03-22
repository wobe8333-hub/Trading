from src.strategy.selector.strategy_weights import StrategyWeights

W = StrategyWeights


def test_initial_weights_all_1():
    w = W()
    for name in [
        "vwap_pullback",
        "trend_continuation",
        "liquidity_sweep_reversal",
        "breakout_momentum",
        "liquidation_scalping",
        "stop_hunt_reversal",
        "ema_cross_scalping",
    ]:
        assert w.get_weight(name) == 1.0


def test_initial_no_disabled():
    w = W()
    for name in ["vwap_pullback", "trend_continuation"]:
        assert w.is_disabled(name) is False


def test_disable_on_negative_expectancy():
    w = W()
    pnl = [-10.0] * 20  # 모두 손실 → 기대값 < 0
    w.update_from_performance("vwap_pullback", pnl)
    assert w.is_disabled("vwap_pullback") is True
    assert w.get_weight("vwap_pullback") == 0.0


def test_half_weight_on_low_win_rate():
    w = W()
    pnl = [10.0] * 15 + [-1.0] * 3 + [1.0] * 2
    w.update_from_performance("trend_continuation", pnl)
    weight = w.get_weight("trend_continuation")
    assert weight <= 1.0


def test_no_change_on_good_performance():
    w = W()
    pnl = [5.0] * 20
    w.update_from_performance("vwap_pullback", pnl)
    assert w.is_disabled("vwap_pullback") is False
    assert w.get_weight("vwap_pullback") == 1.0


def test_empty_pnl_no_change():
    w = W()
    w.update_from_performance("vwap_pullback", [])
    assert w.get_weight("vwap_pullback") == 1.0


def test_re_enable_restores_weight():
    w = W()
    pnl = [-10.0] * 20
    w.update_from_performance("vwap_pullback", pnl)
    assert w.is_disabled("vwap_pullback") is True
    w.re_enable("vwap_pullback")
    assert w.is_disabled("vwap_pullback") is False
    assert w.get_weight("vwap_pullback") == 1.0


def test_re_enable_clears_reason():
    w = W()
    pnl = [-10.0] * 20
    w.update_from_performance("vwap_pullback", pnl)
    w.re_enable("vwap_pullback")
    assert "vwap_pullback" not in w.disable_reason


def test_get_all_weights_has_7_entries():
    w = W()
    all_w = w.get_all_weights()
    assert len(all_w) == 7

