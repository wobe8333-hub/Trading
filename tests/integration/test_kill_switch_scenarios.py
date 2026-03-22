from __future__ import annotations

from src.risk.kill_switch import KillSwitch
from src.risk.daily_loss_guard import DailyLossGuard
from src.risk.streak_guard import StreakGuard
from src.risk.risk_engine import RiskEngine


def _eng():
    return RiskEngine()


def test_scenario_1_daily_loss_limit():
    eng = _eng()
    ok, reason = eng.check_pre_trade(
        "BTCUSDT",
        "TREND_UP",
        -35.0,
        {"daily_loss_limit": -35},
        {"spread_bps": 2.0},
    )
    assert ok is False
    assert "DAILY_LOSS" in reason
    assert eng.kill_switch.is_active is True


def test_scenario_2_consecutive_losses():
    eng = _eng()
    for _ in range(3):
        eng.check_post_trade("BTCUSDT", "TREND_UP", -5.0, 0.0)
    ok, reason = eng.check_pre_trade(
        "BTCUSDT",
        "TREND_UP",
        -5.0,
        {"daily_loss_limit": -35},
        {"spread_bps": 2.0},
    )
    assert ok is False
    assert eng.kill_switch.is_active is True


def test_scenario_3_stop_not_registered():
    ks = KillSwitch()
    ks.trigger("STOP_NOT_REGISTERED")
    assert ks.is_active is True
    assert ks.is_blocked() is True
    released = ks.auto_release()
    assert released is False
    assert ks.is_active is True


def test_scenario_4_api_error():
    ks = KillSwitch()
    ks.trigger("API_ERROR")
    assert ks.is_active is True
    released = ks.auto_release()
    assert released is False


def test_scenario_5_spread_anomaly():
    eng = _eng()
    ok, reason = eng.check_pre_trade(
        "BTCUSDT",
        "TREND_UP",
        -10.0,
        {"daily_loss_limit": -35},
        {"spread_bps": 150.0},
    )
    assert ok is False
    assert "SPREAD" in reason


def test_scenario_6_slippage_anomaly():
    eng = _eng()
    eng.check_post_trade("BTCUSDT", "TREND_UP", 5.0, 10.0)
    assert eng.kill_switch.is_active is True


def test_scenario_7_same_coin_2_losses():
    eng = _eng()
    eng.check_post_trade("BTCUSDT", "TREND_UP", -5.0, 0.0)
    eng.check_post_trade("BTCUSDT", "TREND_UP", -5.0, 0.0)
    assert eng.kill_switch.is_symbol_blocked("BTCUSDT") is True


def test_scenario_8_same_regime_2_losses():
    eng = _eng()
    eng.check_post_trade("BTCUSDT", "EXPANSION", -5.0, 0.0)
    eng.check_post_trade("ETHUSDT", "EXPANSION", -5.0, 0.0)
    assert eng.kill_switch.is_regime_blocked("EXPANSION") is True


def test_kill_switch_manual_release_resumes():
    eng = _eng()
    eng.kill_switch.trigger("CONSECUTIVE_LOSSES", 1.0)
    assert eng.kill_switch.is_active is True
    eng.kill_switch.manual_release()
    ok, _ = eng.check_pre_trade(
        "BTCUSDT",
        "TREND_UP",
        -5.0,
        {"daily_loss_limit": -35},
        {"spread_bps": 2.0},
    )
    assert ok is True

