from src.growth.account_growth_engine import AccountGrowthEngine

ENG = AccountGrowthEngine()

_REQUIRED_KEYS = [
    "stage_id",
    "risk_pct",
    "daily_loss_limit",
    "scale_limit",
    "min_entry_score",
    "is_halted",
    "conservative_mode",
]


# ── 반환 구조 ────────────────────────────────────────────────

def test_returns_required_keys():
    result = ENG.get_trade_parameters(700, 0)
    for k in _REQUIRED_KEYS:
        assert k in result


def test_stage1_at_700():
    result = ENG.get_trade_parameters(700, 0)
    assert result["stage_id"] == 1
    assert abs(result["risk_pct"] - 0.032) < 0.001


def test_stage2_at_1500():
    result = ENG.get_trade_parameters(1500, 0)
    assert result["stage_id"] == 2
    assert abs(result["risk_pct"] - 0.025) < 0.001


# ── profit_lock 반영 ──────────────────────────────────────────

def test_no_lock_at_zero_pnl():
    result = ENG.get_trade_parameters(700, 0)
    assert result["is_halted"] is False
    assert result["scale_limit"] == 1.0


def test_lock_scale_at_20_pnl():
    """구현지침서 PASS 기준: daily_pnl=20 → scale_limit=0.80."""
    result = ENG.get_trade_parameters(700, 20)
    assert abs(result["scale_limit"] - 0.80) < 0.001


def test_halt_at_60_pnl():
    result = ENG.get_trade_parameters(700, 60)
    assert result["is_halted"] is True


# ── stage_transition ──────────────────────────────────────────

def test_check_stage_transition():
    result = ENG.check_stage_transition(1499, 1500)
    assert result["transitioned"] is True
    assert result["from"] == 1
    assert result["to"] == 2


# ── 예외 안전성 ─────────────────────────────────────────────

def test_no_exception_on_extreme_equity():
    result = ENG.get_trade_parameters(0.0, 0.0)
    assert isinstance(result, dict)
    assert "stage_id" in result

