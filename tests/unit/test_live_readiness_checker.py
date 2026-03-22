from src.analytics.live_readiness_checker import LiveReadinessChecker
from src.analytics.analytics_engine import AnalyticsEngine


_REQUIRED_CONDITIONS = [
    "no_critical_errors_2w",
    "kill_switch_all_9_tested",
    "positive_pnl_net_expectancy",
    "latency_under_500ms",
    "zero_sl_tp_missing",
    "win_rate_55_plus",
    "maker_ratio_70_plus",
]


def _make_winning_trades(n=20):
    return [
        {
            "pnl_net": 5.0,
            "r_multiple": 1.5,
            "order_type": "LIMIT",
            "sl_registered": True,
            "strategy": "vwap_pullback",
        }
        for _ in range(n)
    ]


def test_check_all_returns_required_keys():
    checker = LiveReadinessChecker()
    result = checker.check_all()
    assert "ready" in result
    assert "conditions" in result
    assert "summary" in result


def test_check_all_conditions_has_7_keys():
    checker = LiveReadinessChecker()
    result = checker.check_all()
    for key in _REQUIRED_CONDITIONS:
        assert key in result["conditions"], f"missing: {key}"


def test_ready_is_bool():
    checker = LiveReadinessChecker()
    result = checker.check_all()
    assert isinstance(result["ready"], bool)


def test_summary_is_string():
    checker = LiveReadinessChecker()
    result = checker.check_all()
    assert isinstance(result["summary"], str)


def test_latency_ok_under_500ms():
    checker = LiveReadinessChecker(latency_ms=100.0)
    result = checker.check_all()
    assert result["conditions"]["latency_under_500ms"] is True


def test_latency_fail_over_500ms():
    checker = LiveReadinessChecker(latency_ms=600.0)
    result = checker.check_all()
    assert result["conditions"]["latency_under_500ms"] is False


def test_positive_expectancy_with_wins():
    eng = AnalyticsEngine()
    for t in _make_winning_trades(10):
        eng.record_trade(t)
    checker = LiveReadinessChecker(analytics_engine=eng, latency_ms=100.0)
    result = checker.check_all()
    assert result["conditions"]["positive_pnl_net_expectancy"] is True


def test_zero_sl_tp_missing_with_all_registered():
    eng = AnalyticsEngine()
    for t in _make_winning_trades(5):
        eng.record_trade(t)
    checker = LiveReadinessChecker(analytics_engine=eng, latency_ms=100.0)
    result = checker.check_all()
    assert result["conditions"]["zero_sl_tp_missing"] is True


def test_win_rate_55_with_winning_trades():
    eng = AnalyticsEngine()
    for t in _make_winning_trades(20):
        eng.record_trade(t)
    checker = LiveReadinessChecker(analytics_engine=eng, latency_ms=100.0)
    result = checker.check_all()
    assert result["conditions"]["win_rate_55_plus"] is True


def test_maker_ratio_with_limit_orders():
    eng = AnalyticsEngine()
    for t in _make_winning_trades(20):
        eng.record_trade(t)
    checker = LiveReadinessChecker(analytics_engine=eng, latency_ms=100.0)
    result = checker.check_all()
    assert result["conditions"]["maker_ratio_70_plus"] is True


def test_not_ready_without_analytics():
    checker = LiveReadinessChecker(latency_ms=100.0)
    result = checker.check_all()
    assert result["ready"] is False


def test_no_exception_on_empty_analytics():
    eng = AnalyticsEngine()
    checker = LiveReadinessChecker(analytics_engine=eng, latency_ms=100.0)
    result = checker.check_all()
    assert isinstance(result["ready"], bool)

