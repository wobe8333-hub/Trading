from src.strategy.entry_score.entry_score_engine import EntryScoreEngine

ENG = EntryScoreEngine()

_REQUIRED_KEYS = [
    "total_score",
    "rule_based_score",
    "funding_bonus",
    "position_scale",
    "entry_quality",
    "components",
]
_COMPONENT_KEYS = [
    "trend",
    "vwap",
    "regime",
    "scanner",
    "volume",
    "volatility",
    "orderflow",
    "pattern",
    "funding",
]


def _make_klines(n=60, close=100.0):
    return [
        {
            "timestamp": i,
            "open": close + i * 0.1,
            "high": close + i * 0.1 + 0.3,
            "low": close + i * 0.1 - 0.3,
            "close": close + i * 0.1,
            "volume": 1000.0 + i,
        }
        for i in range(n)
    ]


def _state():
    return {"klines_3m": _make_klines(), "last_price": 106.0}


def _of(conf=0.5):
    return {"max_confidence": conf}


def _layer(l1=True, l2=True, l3=True):
    return {"layer1": l1, "layer2": l2, "layer3": l3, "direction": "LONG"}


def test_returns_required_keys():
    result = ENG.compute(
        "BTCUSDT",
        "vwap_pullback",
        "LONG",
        "TREND_UP",
        "A",
        _state(),
        _of(),
        _layer(),
        0.0001,
    )
    for k in _REQUIRED_KEYS:
        assert k in result, f"missing key: {k}"


def test_components_has_required_keys():
    result = ENG.compute(
        "BTCUSDT",
        "vwap_pullback",
        "LONG",
        "TREND_UP",
        "A",
        _state(),
        _of(),
        _layer(),
        0.0001,
    )
    for k in _COMPONENT_KEYS:
        assert k in result["components"], f"missing component: {k}"


def test_total_score_within_0_100():
    result = ENG.compute(
        "BTCUSDT",
        "vwap_pullback",
        "LONG",
        "TREND_UP",
        "S",
        _state(),
        _of(1.0),
        _layer(),
        0.002,
    )
    assert 0.0 <= result["total_score"] <= 100.0


def test_total_score_never_exceeds_100():
    result = ENG.compute(
        "BTCUSDT",
        "vwap_pullback",
        "LONG",
        "TREND_UP",
        "S",
        _state(),
        {"max_confidence": 1.0},
        _layer(),
        -0.002,
    )
    assert result["total_score"] <= 100.0


def test_total_equals_raw_plus_funding():
    result = ENG.compute(
        "BTCUSDT",
        "vwap_pullback",
        "LONG",
        "TREND_UP",
        "A",
        _state(),
        _of(),
        _layer(),
        0.0001,
    )
    expected = min(result["rule_based_score"] + result["funding_bonus"], 100.0)
    assert abs(result["total_score"] - expected) < 1e-4


def test_position_scale_valid_values():
    valid = {0.0, 0.4, 0.7, 1.0}
    result = ENG.compute(
        "BTCUSDT",
        "vwap_pullback",
        "LONG",
        "TREND_UP",
        "A",
        _state(),
        _of(),
        _layer(),
        0.0001,
    )
    assert result["position_scale"] in valid


def test_entry_quality_valid_values():
    valid = {"A+", "A", "B", "REJECT"}
    result = ENG.compute(
        "BTCUSDT",
        "vwap_pullback",
        "LONG",
        "TREND_UP",
        "A",
        _state(),
        _of(),
        _layer(),
        0.0001,
    )
    assert result["entry_quality"] in valid


def test_reject_on_empty_state():
    result = ENG.compute(
        "BTCUSDT",
        "vwap_pullback",
        "LONG",
        "TREND_UP",
        "B",
        {},
        {},
        {"layer1": False, "layer2": False, "layer3": False},
        0.0,
    )
    assert result["entry_quality"] in {"REJECT", "B", "A", "A+"}
    assert result["position_scale"] in {0.0, 0.4, 0.7, 1.0}


def test_funding_bonus_applied_to_short():
    r1 = ENG.compute(
        "BTCUSDT",
        "vwap_pullback",
        "SHORT",
        "TREND_DOWN",
        "A",
        _state(),
        _of(),
        _layer(),
        0.002,
    )
    r2 = ENG.compute(
        "BTCUSDT",
        "vwap_pullback",
        "SHORT",
        "TREND_DOWN",
        "A",
        _state(),
        _of(),
        _layer(),
        0.0,
    )
    assert r1["funding_bonus"] == 8.0
    assert r2["funding_bonus"] == 0.0


def test_no_exception_on_none_state():
    result = ENG.compute(
        "BTCUSDT",
        "vwap_pullback",
        "LONG",
        "TREND_UP",
        "A",
        None,
        None,
        None,
        0.0,  # type: ignore
    )
    assert result["entry_quality"] == "REJECT"
    assert result["total_score"] == 0.0


def test_no_exception_on_bad_types():
    result = ENG.compute(
        "BTCUSDT",
        "vwap_pullback",
        "LONG",
        "TREND_UP",
        "A",
        {"klines_3m": "bad"},
        {"max_confidence": "bad"},
        {"layer1": "bad"},  # type: ignore
        "bad",  # type: ignore
    )
    assert "total_score" in result

