from src.growth.position_scaler import PositionScaler
from src.growth.account_growth_engine import AccountGrowthEngine


def test_step13_pass_criteria():
    """
    구현지침서 STEP 13 공식 PASS 기준:
    ps.compute_position_size(700, 0.032, 50, TREND_UP) → 포지션 크기 출력
    ps.compute_stop_price(43000, 50, TREND_UP, LONG)   → stop 출력
    ps.compute_tp_prices(43000, 50, TREND_UP, LONG)    → tp1, tp2 출력
    """
    ps = PositionScaler()
    size = ps.compute_position_size(700, 0.032, 50, "TREND_UP")
    print(f"포지션 크기: {size:.2f} 계약")
    assert abs(size - 11.2) < 0.01, f"expected 11.2 got {size}"

    stop = ps.compute_stop_price(43000, 50, "TREND_UP", "LONG")
    tp1, tp2 = ps.compute_tp_prices(43000, 50, "TREND_UP", "LONG")
    print(f"Stop: {stop}, TP1: {tp1}, TP2: {tp2}")
    assert stop < 43000
    assert tp1 > 43000
    assert tp2 > tp1
    print("PASS: position_scaler step13 pass criteria")


def test_step14_pass_criteria():
    """
    구현지침서 STEP 14 공식 PASS 기준:
    engine.get_trade_parameters(equity=700, daily_pnl=0)
    engine.get_trade_parameters(equity=700, daily_pnl=20) → scale_limit=0.80
    """
    engine = AccountGrowthEngine()

    params = engine.get_trade_parameters(equity=700, daily_pnl=0)
    print(params)
    assert params["stage_id"] == 1
    assert params["is_halted"] is False

    params2 = engine.get_trade_parameters(equity=700, daily_pnl=20)
    print(params2["scale_limit"])  # 0.80
    assert abs(params2["scale_limit"] - 0.80) < 0.001
    print("PASS: account_growth_engine step14 pass criteria")


def test_all_4_stages():
    """4개 Stage 모두 정상 반환."""
    engine = AccountGrowthEngine()
    for equity, expected_stage in [(700, 1), (1500, 2), (3000, 3), (6000, 4)]:
        result = engine.get_trade_parameters(equity=equity, daily_pnl=0)
        assert result["stage_id"] == expected_stage


def test_position_size_all_regimes():
    """4개 Regime에서 모두 양수 포지션 사이즈 반환."""
    ps = PositionScaler()
    for regime in ["TREND_UP", "TREND_DOWN", "RANGE", "EXPANSION"]:
        size = ps.compute_position_size(700, 0.032, 50, regime)
        assert size > 0, f"regime={regime} size={size}"


def test_50_consecutive_no_exception():
    """50회 연속 실행 — 예외 없음."""
    ps = PositionScaler()
    eng = AccountGrowthEngine()
    for i in range(50):
        size = ps.compute_position_size(700 + i * 10, 0.032, 50, "TREND_UP")
        result = eng.get_trade_parameters(700 + i * 10, float(i))
        assert isinstance(size, float)
        assert isinstance(result, dict)

