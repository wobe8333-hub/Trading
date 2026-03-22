from datetime import datetime, timezone
from src.core.execution_cost_guard.cost_guard import ExecutionCostGuard
from src.app.config_loader import get_config
from src.core.market_data.market_data_manager import MarketDataManager

_VALID_REASONS = {"PASS", "LIQUIDITY", "FUNDING_TIME", "COST_EXCEED", "GUARD_ERROR"}


def test_cost_guard_smoke_with_paper_mode():
    """paper_mode BTC state → 유효한 check() 결과 반환."""
    cfg = get_config()
    mdm = MarketDataManager(cfg)
    mdm.initialize(["BTCUSDT"])

    btc_state = mdm.get_state("BTCUSDT") or {}
    guard     = ExecutionCostGuard()
    now_utc   = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)

    ok, detail = guard.check(
        symbol="BTCUSDT", order_type="LIMIT",
        order_size_usd=175.0,
        tp1_price=66000.0, entry_price=65000.0,
        regime="TREND_UP",
        now_utc=now_utc,
        funding_rate=0.0001,
        entry_score=75,
        market_state=btc_state,
    )
    assert isinstance(ok, bool)
    assert detail["reason"] in _VALID_REASONS


def test_cost_calculator_integration():
    """TP1 기준 비용 비율 계산 정확성."""
    from src.core.execution_cost_guard.cost_calculator import CostCalculator
    calc = CostCalculator()

    result = calc.compute_total_cost_bps(
        "BTCUSDT", "LIMIT", 175.0,
        {"spread_bps": 2.0, "orderbook_depth_usd": 500_000.0},
        "TREND_UP",
    )
    # fee=4 + spread=1 + slippage=0.0525 → total ≈ 5.05bps
    assert result["total_cost_bps"] > 0
    assert result["fee_bps"] == 4.0

    # TP1 거리 ≈ 116bps(65000→66000), threshold=116*0.2=23.2bps
    ok = CostCalculator.is_cost_acceptable(result["total_cost_bps"], 116.0)
    assert ok is True


def test_50_consecutive_no_exception():
    """50회 연속 실행 — 예외 없음."""
    guard   = ExecutionCostGuard()
    now_utc = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    for _ in range(50):
        ok, detail = guard.check(
            "BTCUSDT", "LIMIT", 175.0,
            43500.0, 43000.0, "RANGE",
            now_utc, 0.0001, 75, {},
        )
        assert isinstance(ok, bool)
        assert detail["reason"] in _VALID_REASONS


def test_pass_criteria():
    """
    구현지침서 공식 PASS 기준:
    g.check(symbol, LIMIT, 175, tp1=43500, entry=43000, ...) → (bool, reason)
    """
    guard   = ExecutionCostGuard()
    now_utc = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    mock_state = {
        "spread_bps": 2.0,
        "orderbook_depth_usd": 500_000.0,
    }
    ok, detail = guard.check(
        symbol="BTCUSDT", order_type="LIMIT",
        order_size_usd=175.0,
        tp1_price=43500.0, entry_price=43000.0,
        regime="TREND_UP",
        now_utc=now_utc,
        funding_rate=0.0001,
        entry_score=75,
        market_state=mock_state,
    )
    print(ok, detail["reason"])
    assert detail["reason"] in _VALID_REASONS
    print("PASS: cost_guard pass criteria")

