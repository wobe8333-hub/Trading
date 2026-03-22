from src.core.coin_scanner.coin_classifier import CoinClassifier

CLASSIFIER = CoinClassifier()


def test_btcusdt_is_core():
    result = CLASSIFIER.classify_all(["BTCUSDT"], [], {})
    assert result["BTCUSDT"] == "CORE"


def test_ethusdt_is_core():
    result = CLASSIFIER.classify_all(["ETHUSDT"], [], {})
    assert result["ETHUSDT"] == "CORE"


def test_funding_extreme():
    ms = {"funding_rate": 0.001}   # >= 0.0005 threshold
    result = CLASSIFIER.classify_all(["XRPUSDT"], [], {"XRPUSDT": ms})
    assert result["XRPUSDT"] == "FUNDING_EXTREME"


def test_range_play_fallback_on_empty_data():
    result = CLASSIFIER.classify_all(["UNKNOWN"], [], {})
    assert result["UNKNOWN"] == "RANGE_PLAY"


def test_all_symbols_classified():
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]
    result = CLASSIFIER.classify_all(symbols, [], {})
    assert set(result.keys()) == set(symbols)
    valid_types = {"CORE", "HIGH_BETA", "INDEPENDENT", "RANGE_PLAY", "FUNDING_EXTREME"}
    for sym, t in result.items():
        assert t in valid_types, f"{sym}: {t}"


def test_compute_beta_empty_data():
    beta = CLASSIFIER.compute_beta("BTCUSDT", [], {})
    assert beta == 0.0
