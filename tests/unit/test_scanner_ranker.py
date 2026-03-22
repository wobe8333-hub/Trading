from src.core.coin_scanner.scanner_ranker import ScannerRanker, _grade

RANKER = ScannerRanker()


def _make_features(symbol: str, score: float) -> dict:
    return {
        "symbol": symbol, "total_score": score,
        "liquidity_score": 0, "volatility_score": 0, "momentum_score": 0,
        "participation_score": 0, "orderbook_quality": 0,
        "funding_imbalance_score": 0, "event_score": 0,
        "raw": {},
    }


def test_grade_s():
    assert _grade(95.0) == "S"
    assert _grade(90.0) == "S"


def test_grade_a():
    assert _grade(89.0) == "A"
    assert _grade(80.0) == "A"


def test_grade_b():
    assert _grade(79.0) == "B"
    assert _grade(70.0) == "B"


def test_below_min_score_excluded():
    features = {
        "BTCUSDT": _make_features("BTCUSDT", 24.9),
        "ETHUSDT": _make_features("ETHUSDT", 80.0),
    }
    result = RANKER.rank_all(features)
    syms = [r["symbol"] for r in result]
    assert "BTCUSDT" not in syms
    assert "ETHUSDT" in syms


def test_sorted_descending():
    features = {
        "A": _make_features("A", 75.0),
        "B": _make_features("B", 90.0),
        "C": _make_features("C", 82.0),
    }
    result = RANKER.rank_all(features)
    scores = [r["score"] for r in result]
    assert scores == sorted(scores, reverse=True)


def test_returns_required_keys():
    features = {"BTCUSDT": _make_features("BTCUSDT", 85.0)}
    result = RANKER.rank_all(features)
    assert len(result) == 1
    for key in ["symbol", "score", "grade", "features"]:
        assert key in result[0]


def test_empty_features_returns_empty():
    assert RANKER.rank_all({}) == []
