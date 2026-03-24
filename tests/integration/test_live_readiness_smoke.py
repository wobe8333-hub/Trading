from src.analytics.live_readiness_checker import LiveReadinessChecker
from src.analytics.analytics_engine import AnalyticsEngine
from src.utils.logger import get_logger
from src.utils.time_utils import now_utc, to_utc, format_duration
from datetime import timezone


def test_step22_pass_criteria():
    checker = LiveReadinessChecker()
    result = checker.check_all()
    assert "ready" in result
    assert "conditions" in result
    assert "summary" in result


def test_full_readiness_with_winning_history():
    import tempfile, os
    tmp_dir = tempfile.mkdtemp()
    from unittest.mock import patch
    with patch("src.analytics.analytics_engine._TRADE_DIR", tmp_dir):
        eng = AnalyticsEngine()
    eng._persist = lambda trade: None  # 테스트 중 파일 쓰기 방지
    for _ in range(20):
        eng.record_trade(
            {
                "pnl_net": 10.0,
                "r_multiple": 1.5,
                "order_type": "LIMIT",
                "sl_registered": True,
                "strategy": "vwap_pullback",
            }
        )

    checker = LiveReadinessChecker(analytics_engine=eng, latency_ms=200.0)
    result = checker.check_all()

    assert result["conditions"]["latency_under_500ms"] is True
    assert result["conditions"]["positive_pnl_net_expectancy"] is True
    assert result["conditions"]["win_rate_55_plus"] is True
    assert result["conditions"]["maker_ratio_70_plus"] is True
    assert result["conditions"]["zero_sl_tp_missing"] is True


def test_logger_util():
    lg = get_logger("test.logger", "app")
    assert lg is not None
    lg.info("test log message")


def test_time_utils():
    now = now_utc()
    assert now.tzinfo is not None
    dt = to_utc(1700000000.0)
    assert dt.tzinfo.utcoffset(dt).total_seconds() == 0
    assert format_duration(3725.0) == "1h 2m 5s"
    assert format_duration(65.0) == "1m 5s"
    assert format_duration(10.0) == "10s"

