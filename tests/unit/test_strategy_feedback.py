from src.strategy.selector.strategy_feedback import StrategyFeedback
from src.strategy.selector.strategy_weights import StrategyWeights


def _fb():
    w = StrategyWeights()
    return StrategyFeedback(w), w


def test_record_and_history():
    fb, _ = _fb()
    fb.record("vwap_pullback", "BTCUSDT", "TREND_UP", 10.0, 1.5)
    hist = fb.get_history("vwap_pullback")
    assert len(hist) == 1
    assert hist[0]["pnl_net"] == 10.0


def test_record_multiple_strategies():
    fb, _ = _fb()
    fb.record("vwap_pullback", "BTCUSDT", "TREND_UP", 5.0, 1.2)
    fb.record("trend_continuation", "ETHUSDT", "RANGE", -2.0, 0.8)
    assert len(fb.get_history("vwap_pullback")) == 1
    assert len(fb.get_history("trend_continuation")) == 1


def test_expectancy_positive():
    fb, _ = _fb()
    for _ in range(5):
        fb.record("vwap_pullback", "BTCUSDT", "TREND_UP", 10.0, 1.5)
    assert fb.get_recent_expectancy("vwap_pullback") == 10.0


def test_expectancy_zero_on_empty():
    fb, _ = _fb()
    assert fb.get_recent_expectancy("vwap_pullback") == 0.0


def test_expectancy_last_n():
    fb, _ = _fb()
    for i in range(25):
        fb.record("vwap_pullback", "BTCUSDT", "TREND_UP", float(i), 1.0)
    exp = fb.get_recent_expectancy("vwap_pullback", n=20)
    assert abs(exp - 14.5) < 0.01


def test_win_rate_all_wins():
    fb, _ = _fb()
    for _ in range(10):
        fb.record("vwap_pullback", "BTCUSDT", "TREND_UP", 5.0, 1.0)
    assert fb.get_recent_win_rate("vwap_pullback") == 1.0


def test_win_rate_half():
    fb, _ = _fb()
    for i in range(10):
        pnl = 5.0 if i % 2 == 0 else -5.0
        fb.record("vwap_pullback", "BTCUSDT", "TREND_UP", pnl, 1.0)
    assert fb.get_recent_win_rate("vwap_pullback") == 0.5


def test_win_rate_1_on_empty():
    fb, _ = _fb()
    assert fb.get_recent_win_rate("vwap_pullback") == 1.0


def test_trigger_disables_on_negative_expectancy():
    fb, w = _fb()
    for _ in range(25):
        fb.record("vwap_pullback", "BTCUSDT", "TREND_UP", -5.0, 0.5)
    fb.trigger_weight_update()
    assert w.is_disabled("vwap_pullback") is True

