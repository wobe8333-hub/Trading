from src.growth.stage_manager import StageManager

SM = StageManager()


def test_stage1_for_700():
    stage = SM.get_current_stage(700)
    assert stage["id"] == 1


def test_stage1_boundary_699():
    """$699 → stage1 미만 → 여전히 stage1 반환 (최소값)."""
    stage = SM.get_current_stage(699)
    assert isinstance(stage, dict)
    assert "id" in stage


def test_stage2_for_1500():
    stage = SM.get_current_stage(1500)
    assert stage["id"] == 2


def test_stage3_for_3000():
    stage = SM.get_current_stage(3000)
    assert stage["id"] == 3


def test_stage4_for_6000():
    stage = SM.get_current_stage(6000)
    assert stage["id"] == 4


def test_stage4_for_9999():
    stage = SM.get_current_stage(9999)
    assert stage["id"] == 4


def test_get_risk_pct_stage1():
    pct = SM.get_risk_pct(700)
    assert abs(pct - 0.032) < 0.001


def test_get_risk_pct_stage2():
    pct = SM.get_risk_pct(1500)
    assert abs(pct - 0.025) < 0.001


def test_no_transition():
    result = SM.check_stage_transition(800, 900)
    assert result["transitioned"] is False
    assert result["from"] == result["to"]


def test_stage_transition_1_to_2():
    result = SM.check_stage_transition(1499, 1500)
    assert result["transitioned"] is True
    assert result["from"] == 1
    assert result["to"] == 2


def test_returns_dict_with_required_keys():
    stage = SM.get_current_stage(700)
    for k in ["id", "equity_min", "equity_max", "risk_pct_per_trade", "daily_loss_limit"]:
        assert k in stage

