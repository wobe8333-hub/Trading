from src.core.coin_scanner.macro_coin_selector import MacroCoinSelector

SELECTOR = MacroCoinSelector()


def _make_ranked(symbol: str, score: float) -> dict:
    return {"symbol": symbol, "score": score, "grade": "A", "features": {}}


def _types(**kwargs) -> dict:
    return kwargs


def test_risk_off_returns_empty():
    ranked = [_make_ranked("BTCUSDT", 90.0)]
    result = SELECTOR.select_top3(ranked, {"BTCUSDT": "CORE"}, "RISK_OFF")
    assert result == []


def test_bull_core_plus_high_beta():
    ranked = [
        _make_ranked("BTCUSDT", 92.0),
        _make_ranked("SOLUSDT", 85.0),
        _make_ranked("AVAXUSDT", 82.0),
    ]
    coin_types = {
        "BTCUSDT": "CORE",
        "SOLUSDT": "HIGH_BETA",
        "AVAXUSDT": "HIGH_BETA",
    }
    result = SELECTOR.select_top3(ranked, coin_types, "BULL")
    syms = [r["symbol"] for r in result]
    assert "BTCUSDT" in syms
    assert len(result) <= 3


def test_bear_composition():
    ranked = [
        _make_ranked("BTCUSDT", 90.0),
        _make_ranked("SOLUSDT", 82.0),
        _make_ranked("LINKUSDT", 80.0),
    ]
    coin_types = {
        "BTCUSDT":  "CORE",
        "SOLUSDT":  "HIGH_BETA",
        "LINKUSDT": "INDEPENDENT",
    }
    result = SELECTOR.select_top3(ranked, coin_types, "BEAR")
    assert len(result) <= 3
    syms = [r["symbol"] for r in result]
    assert "BTCUSDT" in syms


def test_no_duplicate_symbols():
    ranked = [
        _make_ranked("BTCUSDT", 90.0),
        _make_ranked("ETHUSDT", 85.0),
    ]
    coin_types = {"BTCUSDT": "CORE", "ETHUSDT": "CORE"}
    result = SELECTOR.select_top3(ranked, coin_types, "BULL")
    syms = [r["symbol"] for r in result]
    assert len(syms) == len(set(syms))


def test_slot_skipped_when_no_candidate():
    # HIGH_BETA 코인이 없으면 해당 슬롯 제외
    ranked = [_make_ranked("BTCUSDT", 90.0)]
    coin_types = {"BTCUSDT": "CORE"}
    result = SELECTOR.select_top3(ranked, coin_types, "BULL")
    assert len(result) <= 3
    assert all("symbol" in r for r in result)


def test_result_has_coin_type_field():
    ranked = [_make_ranked("BTCUSDT", 90.0)]
    coin_types = {"BTCUSDT": "CORE"}
    result = SELECTOR.select_top3(ranked, coin_types, "BULL")
    for r in result:
        assert "coin_type" in r
