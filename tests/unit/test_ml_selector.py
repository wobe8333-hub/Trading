from src.strategy.selector.ml_selector import MLStrategySelector


def test_is_active_always_false():
    ml = MLStrategySelector()
    assert ml.is_active() is False


def test_adjust_weights_passthrough():
    ml = MLStrategySelector()
    scores = {"vwap_pullback": 1.2, "trend_continuation": 0.8}
    result = ml.adjust_weights(scores)
    assert result == scores


def test_get_status_keys():
    ml = MLStrategySelector()
    status = ml.get_status()
    assert "active" in status
    assert "activation_condition" in status
    assert "current_trade_count" in status


def test_get_status_active_false():
    ml = MLStrategySelector()
    assert ml.get_status()["active"] is False


def test_update_trade_count():
    ml = MLStrategySelector()
    ml.update_trade_count(123)
    assert ml.get_status()["current_trade_count"] == 123

