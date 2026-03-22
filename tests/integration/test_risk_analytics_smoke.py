from src.risk.risk_engine import RiskEngine
from src.risk.drawdown_manager import DrawdownManager
from src.analytics.analytics_engine import AnalyticsEngine
from src.analytics.expectancy_engine import ExpectancyEngine
from src.analytics.target_tracker import TargetTracker


def _make_trade(pnl=5.0):
    return {
        "timestamp": "2024-01-01T00:00:00Z",
        "symbol": "BTCUSDT",
        "strategy": "vwap_pullback",
        "regime": "TREND_UP",
        "pnl_net": pnl,
        "r_multiple": 1.5,
        "strategy_layer_hit": {"layer1": True, "layer2": True, "layer3": True},
    }


def test_step15_kill_switch_pass_criteria():
    from src.risk.kill_switch import KillSwitch

    ks = KillSwitch()
    ks.trigger("CONSECUTIVE_LOSSES", 1.0)
    assert ks.is_blocked() is True


def test_step16_drawdown_pass_criteria():
    dm = DrawdownManager()
    dm.update_equity(700)
    dm.update_equity(595)  # -15% → ALERT
    dm.update_equity(455)  # -35% → HALT
    assert dm.get_state() == "HALT"


def test_step17_analytics_pass_criteria():
    engine = AnalyticsEngine()
    engine.record_trade(_make_trade())
    count = engine.get_total_trade_count()
    assert count == 1


def test_expectancy_integration():
    trades = [_make_trade(pnl) for pnl in [10, -5, 8, -3, 12]]
    ee = ExpectancyEngine()
    result = ee.compute_expectancy(trades)
    assert 0.0 <= result["win_rate"] <= 1.0
    assert result["total_trades"] == 5


def test_target_tracker_integration():
    trades = [_make_trade(50.0)] * 10
    tt = TargetTracker()
    result = tt.compute(800, 700, 10000, trades, 5.0)
    assert result["remaining_amount"] == 9200.0
    assert "estimated_completion_days" in result


def test_risk_engine_full_pipeline():
    eng = RiskEngine()
    ok, _ = eng.check_pre_trade(
        "BTCUSDT",
        "TREND_UP",
        -10.0,
        {"daily_loss_limit": -35},
        {"spread_bps": 2.0},
    )
    assert ok is True
    eng.check_post_trade("BTCUSDT", "TREND_UP", 5.0, 2.0)
    ok2, _ = eng.check_pre_trade(
        "BTCUSDT",
        "TREND_UP",
        -10.0,
        {"daily_loss_limit": -35},
        {"spread_bps": 2.0},
    )
    assert isinstance(ok2, bool)

