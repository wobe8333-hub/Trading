from src.risk.kill_switch import KillSwitch
from src.risk.daily_loss_guard import DailyLossGuard
from src.risk.streak_guard import StreakGuard
from src.risk.risk_engine import RiskEngine
from src.risk.drawdown_manager import DrawdownManager
from src.risk.recovery_engine import RecoveryEngine


def test_kill_switch_trigger_blocks():
    ks = KillSwitch()
    ks.trigger("CONSECUTIVE_LOSSES", cooldown_hours=1.0)
    assert ks.is_active is True
    assert ks.is_blocked() is True


def test_kill_switch_manual_release():
    ks = KillSwitch()
    ks.trigger("CONSECUTIVE_LOSSES", 1.0)
    ks.manual_release()
    assert ks.is_active is False
    assert ks.is_blocked() is False


def test_kill_switch_symbol_block_unblock():
    ks = KillSwitch()
    ks.block_symbol("BTCUSDT", hours=0.0001)
    assert ks.is_symbol_blocked("BTCUSDT") is True
    import time

    # hours=0.0001 == 0.36 seconds 이므로 충분히 대기
    time.sleep(0.4)
    assert ks.is_symbol_blocked("BTCUSDT") is False


def test_kill_switch_regime_block():
    ks = KillSwitch()
    ks.block_regime("EXPANSION", hours=1.0)
    assert ks.is_regime_blocked("EXPANSION") is True
    assert ks.is_regime_blocked("TREND_UP") is False


def test_manual_only_reason_no_auto_release():
    ks = KillSwitch()
    ks.trigger("STOP_NOT_REGISTERED")
    ks.cooldown_until = None
    result = ks.auto_release()
    assert result is False
    assert ks.is_active is True


def test_daily_loss_guard_pass():
    ks = KillSwitch()
    g = DailyLossGuard(ks)
    ok, _ = g.check(-10.0, {"daily_loss_limit": -35})
    assert ok is True


def test_daily_loss_guard_blocked():
    ks = KillSwitch()
    g = DailyLossGuard(ks)
    ok, _ = g.check(-35.0, {"daily_loss_limit": -35})
    assert ok is False
    assert ks.is_active is True


def test_streak_guard_3_losses():
    ks = KillSwitch()
    sg = StreakGuard(ks)
    for _ in range(3):
        sg.record_trade(-5.0, "BTCUSDT", "TREND_UP")
    ok, _ = sg.check()
    assert ok is False
    assert ks.is_active is True


def test_streak_guard_reset_on_win():
    ks = KillSwitch()
    sg = StreakGuard(ks)
    sg.record_trade(-5.0, "BTCUSDT", "TREND_UP")
    sg.record_trade(-5.0, "BTCUSDT", "TREND_UP")
    sg.record_trade(10.0, "BTCUSDT", "TREND_UP")  # 이익 → 리셋
    assert sg.consecutive_losses == 0


def test_risk_engine_pre_trade_pass():
    eng = RiskEngine()
    ok, _ = eng.check_pre_trade(
        "BTCUSDT",
        "TREND_UP",
        -10.0,
        {"daily_loss_limit": -35},
        {"spread_bps": 2.0},
    )
    assert ok is True


def test_risk_engine_kill_switch_blocks():
    eng = RiskEngine()
    eng.kill_switch.trigger("CONSECUTIVE_LOSSES", 1.0)
    ok, _ = eng.check_pre_trade(
        "BTCUSDT",
        "TREND_UP",
        -10.0,
        {"daily_loss_limit": -35},
        {"spread_bps": 2.0},
    )
    assert ok is False


def test_drawdown_normal():
    dm = DrawdownManager()
    dm.update_equity(700)
    dm.update_equity(700)
    assert dm.get_state() == "NORMAL"
    assert dm.get_drawdown_pct() == 0.0


def test_drawdown_alert():
    dm = DrawdownManager()
    dm.update_equity(700)
    dm.update_equity(595)  # -15% → ALERT
    assert dm.get_state() == "ALERT"


def test_drawdown_halt():
    dm = DrawdownManager()
    dm.update_equity(700)
    dm.update_equity(455)  # -35% → HALT
    assert dm.get_state() == "HALT"
    adj = dm.get_risk_adjustment()
    assert adj["risk_multiplier"] == 0.0


def test_drawdown_risk_adjustment_normal():
    dm = DrawdownManager()
    dm.update_equity(700)
    adj = dm.get_risk_adjustment()
    assert adj["risk_multiplier"] == 1.0
    assert adj["max_strategies"] == 6


def test_recovery_progress_0():
    re = RecoveryEngine()
    p = RecoveryEngine.compute_recovery_progress(600, 700, 600)
    assert p == 0.0


def test_recovery_progress_1():
    p = RecoveryEngine.compute_recovery_progress(700, 700, 600)
    assert p == 1.0


def test_recovery_risk_pct_below_50():
    re = RecoveryEngine()
    result = re.get_recovery_risk_pct("DANGER", 0.032, 0.3)
    assert abs(result - 0.016) < 0.0001


def test_recovery_risk_pct_full():
    re = RecoveryEngine()
    result = re.get_recovery_risk_pct("NORMAL", 0.032, 1.0)
    assert result == 0.032

