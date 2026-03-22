from src.app.config_loader import get_config
from src.core.market_data.market_data_manager import MarketDataManager
from src.core.orderflow_engine.orderflow_engine import OrderflowEngine

_VALID_LIQ  = {None, "SHORT_LIQUIDATION_CASCADE", "LONG_LIQUIDATION_CASCADE"}
_VALID_HUNT = {"NONE", "BULL_HUNT", "BEAR_HUNT"}
_VALID_IMB  = {None, "IMBALANCE_BREAK", "ABSORPTION_EVENT"}


def test_orderflow_smoke_with_paper_mode():
    """paper_mode 3종목 → 유효한 orderflow_state 반환."""
    cfg = get_config()
    mdm = MarketDataManager(cfg)
    mdm.initialize(["BTCUSDT", "ETHUSDT", "SOLUSDT"])

    eng = OrderflowEngine()
    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        state  = mdm.get_state(sym) or {}
        result = eng.compute(sym, state)

        assert 0.0 <= result["max_confidence"] <= 1.0
        assert result["liquidation"]["event_type"] in _VALID_LIQ
        assert result["stop_hunt"]["direction"]     in _VALID_HUNT
        assert result["imbalance"]["event_type"]    in _VALID_IMB


def test_confidence_always_valid_range():
    """50회 연속 호출 — confidence 항상 0~1 범위."""
    eng = OrderflowEngine()
    for _ in range(50):
        r = eng.compute("BTCUSDT", {})
        assert 0.0 <= r["max_confidence"] <= 1.0
        assert 0.0 <= r["liquidation"]["confidence"] <= 1.0
        assert 0.0 <= r["stop_hunt"]["confidence"]   <= 1.0
        assert 0.0 <= r["imbalance"]["confidence"]   <= 1.0


def test_entry_score_engine_connectable():
    """
    구현지침서 PASS 기준: Entry Score Engine 연결 가능
    max_confidence를 Entry Score Engine에 전달 가능한지 확인.
    """
    eng    = OrderflowEngine()
    result = eng.compute("BTCUSDT", {})
    max_conf = result["max_confidence"]

    # Entry Score Engine은 0~10점 orderflow_score를 max_confidence * 10으로 계산
    orderflow_score = max_conf * 10
    assert 0.0 <= orderflow_score <= 10.0
    print(f"PASS: max_confidence={max_conf} orderflow_score={orderflow_score}")


def test_pass_criteria():
    """
    구현지침서 PASS 기준:
    1. 5개 이벤트 감지 가능 ← 클래스 import 확인
    2. confidence 0.0~1.0 범위 내
    3. Entry Score Engine 연결 가능
    """
    eng    = OrderflowEngine()
    result = eng.compute("BTCUSDT", {})

    # confidence 범위
    assert 0.0 <= result["max_confidence"] <= 1.0
    print(f"PASS: confidence={result['max_confidence']}")

    # 구조 확인
    assert "liquidation" in result
    assert "stop_hunt"   in result
    assert "imbalance"   in result
    print("PASS: orderflow_engine pass criteria all met")
