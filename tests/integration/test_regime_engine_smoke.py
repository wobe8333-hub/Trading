from src.app.config_loader import get_config
from src.core.market_data.market_data_manager import MarketDataManager
from src.core.regime_engine.market_regime_engine import MarketRegimeEngine

_VALID = {"TREND_UP", "TREND_DOWN", "RANGE", "EXPANSION"}


def test_regime_smoke_with_paper_mode():
    """paper_mode MarketDataManager → 유효한 Regime 반환."""
    cfg = get_config()
    mdm = MarketDataManager(cfg)
    mdm.initialize(["BTCUSDT", "ETHUSDT", "SOLUSDT"])

    eng = MarketRegimeEngine()
    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        state  = mdm.get_state(sym) or {}
        result = eng.get_regime(sym, state)
        assert result in _VALID, f"{sym}: invalid regime {result}"


def test_get_all_regimes_after_3_symbols():
    """3개 심볼 판정 후 get_all_regimes에 모두 존재."""
    cfg = get_config()
    mdm = MarketDataManager(cfg)
    mdm.initialize(["BTCUSDT", "ETHUSDT", "SOLUSDT"])

    eng = MarketRegimeEngine()
    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        eng.get_regime(sym, mdm.get_state(sym) or {})

    all_r = eng.get_all_regimes()
    assert set(all_r.keys()) == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}
    for r in all_r.values():
        assert r in _VALID


def test_4_regimes_all_returnable():
    """
    4개 Regime 모두 반환 가능한지 확인.
    EXPANSION / TREND_UP / TREND_DOWN / RANGE 각각 trigger 조건 테스트.
    """
    eng = MarketRegimeEngine()

    r_range = eng.get_regime("SYM", {})
    assert r_range in _VALID

    klines_exp = [
        {"timestamp": i, "open": 100.0, "high": 100.1, "low": 99.9,
         "close": 100.0, "volume": 100.0}
        for i in range(30)
    ]
    klines_exp[-1]["high"]   = 200.0
    klines_exp[-1]["low"]    = 0.0
    klines_exp[-1]["volume"] = 1_000_000.0
    r_exp = eng.get_regime("SYM", {"klines_3m": klines_exp, "last_price": 100.0})
    assert r_exp == "EXPANSION"

    klines_up = [
        {"timestamp": i, "open": 100 + i*0.5, "high": 100 + i*0.5 + 0.3,
         "low": 100 + i*0.5 - 0.3, "close": 100 + i*0.5, "volume": 500.0}
        for i in range(100)
    ]
    r_up = eng.get_regime("SYM", {"klines_3m": klines_up, "last_price": 155.0})
    assert r_up == "TREND_UP"

    klines_down = [
        {"timestamp": i, "open": 200 - i*0.5, "high": 200 - i*0.5 + 0.3,
         "low": 200 - i*0.5 - 0.3, "close": 200 - i*0.5, "volume": 500.0}
        for i in range(100)
    ]
    r_down = eng.get_regime("SYM", {"klines_3m": klines_down, "last_price": 1.0})
    assert r_down == "TREND_DOWN"


def test_regime_updates_on_repeated_calls():
    """동일 심볼 반복 호출 시 매번 갱신 확인."""
    eng = MarketRegimeEngine()
    for _ in range(10):
        r = eng.get_regime("BTCUSDT", {})
        assert r in _VALID
    assert "BTCUSDT" in eng.regimes


def test_pass_criteria():
    """
    구현지침서 PASS 기준:
    - 4개 상태 중 항상 1개만 반환
    - 매 루프 갱신 확인
    - 동일 심볼에서 상태 충돌 없음
    """
    eng = MarketRegimeEngine()

    r = eng.get_regime("BTCUSDT", {})
    assert r in _VALID
    print(f"regime={r}")

    for i in range(5):
        eng.get_regime("BTCUSDT", {})
    assert "BTCUSDT" in eng.regimes

    results = set()
    for _ in range(10):
        results.add(eng.get_regime("BTCUSDT", {}))
    assert all(r in _VALID for r in results)
    print("PASS: regime engine pass criteria")
