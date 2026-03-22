from src.growth.profit_lock_manager import ProfitLockManager

_LOCKS_S1 = [
    {"threshold": 20, "scale_pct": 0.80, "min_entry_score": 70},
    {"threshold": 35, "scale_pct": 0.60, "min_entry_score": 75},
    {"threshold": 50, "scale_pct": 0.40, "min_entry_score": 80, "conservative_mode": True},
    {"threshold": 60, "halt": True},
]


def _pm():
    return ProfitLockManager()


# ── check_profit_lock ───────────────────────────────────────

def test_no_lock_below_threshold():
    pm = _pm()
    result = pm.check_profit_lock(10.0, 1, _LOCKS_S1)
    assert result["halt"] is False
    assert result["scale_limit"] == 1.0


def test_lock_at_20():
    pm = _pm()
    result = pm.check_profit_lock(20.0, 1, _LOCKS_S1)
    assert result["halt"] is False
    assert abs(result["scale_limit"] - 0.80) < 0.001
    assert result["min_entry_score"] == 70


def test_lock_at_35():
    pm = _pm()
    result = pm.check_profit_lock(35.0, 1, _LOCKS_S1)
    assert abs(result["scale_limit"] - 0.60) < 0.001
    assert result["min_entry_score"] == 75


def test_lock_at_50_conservative():
    pm = _pm()
    result = pm.check_profit_lock(50.0, 1, _LOCKS_S1)
    assert abs(result["scale_limit"] - 0.40) < 0.001
    assert result["conservative_mode"] is True


def test_halt_at_60():
    pm = _pm()
    result = pm.check_profit_lock(60.0, 1, _LOCKS_S1)
    assert result["halt"] is True
    assert result["scale_limit"] == 0.0


def test_halt_above_60():
    pm = _pm()
    result = pm.check_profit_lock(100.0, 1, _LOCKS_S1)
    assert result["halt"] is True


def test_no_locks_returns_default():
    pm = _pm()
    result = pm.check_profit_lock(100.0, 1, [])
    assert result["halt"] is False
    assert result["scale_limit"] == 1.0


# ── update / reset ───────────────────────────────────────────

def test_update_daily_pnl():
    pm = _pm()
    pm.update_daily_pnl(10.0)
    pm.update_daily_pnl(5.0)
    assert abs(pm.daily_pnl_net - 15.0) < 0.001


def test_reset_daily():
    pm = _pm()
    pm.update_daily_pnl(50.0)
    pm.is_halted = True
    pm.reset_daily()
    assert pm.daily_pnl_net == 0.0
    assert pm.is_halted is False
    assert pm.current_scale_limit == 1.0

