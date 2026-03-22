from src.strategy.entry_score.score_components import ScoreComponents

SC = ScoreComponents()

_REQUIRED_COMPONENT_KEYS = [
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


def _make_klines(n=60, close=100.0, direction="up"):
    klines = []
    for i in range(n):
        c = close + (i * 0.5 if direction == "up" else -i * 0.5)
        klines.append(
            {
                "timestamp": i,
                "open": c - 0.1,
                "high": c + 0.3,
                "low": c - 0.3,
                "close": c,
                "volume": 1000.0 + i,
            }
        )
    return klines


def _state(n=60, direction="up"):
    return {
        "klines_3m": _make_klines(n, direction=direction),
        "last_price": 130.0 if direction == "up" else 70.0,
    }


def _of(conf=0.0):
    return {"max_confidence": conf}


def _layer(all_true=False):
    return {"layer1": all_true, "layer2": all_true, "layer3": all_true}


# ── Trend Score ──────────────────────────────────────────────


def test_trend_score_range():
    score = SC.compute_trend_score(_state(), "LONG")
    assert 0.0 <= score <= 15.0


def test_trend_score_zero_on_empty():
    score = SC.compute_trend_score({}, "LONG")
    assert score == 0.0


# ── VWAP Score ───────────────────────────────────────────────


def test_vwap_score_range():
    score = SC.compute_vwap_score(_state(), "LONG")
    assert 0.0 <= score <= 15.0


def test_vwap_score_zero_on_empty():
    score = SC.compute_vwap_score({}, "LONG")
    assert score == 0.0


# ── Regime Alignment Score ───────────────────────────────────


def test_regime_allowed_returns_15():
    score = SC.compute_regime_alignment_score("vwap_pullback", "TREND_UP")
    assert score == 15.0


def test_regime_forbidden_returns_0():
    score = SC.compute_regime_alignment_score("vwap_pullback", "EXPANSION")
    assert score == 0.0


def test_regime_unknown_returns_0():
    score = SC.compute_regime_alignment_score("vwap_pullback", "UNKNOWN")
    assert score == 0.0


# ── Scanner Bonus ────────────────────────────────────────────


def test_scanner_bonus_S():
    assert ScoreComponents.compute_scanner_bonus("S") == 15.0


def test_scanner_bonus_A():
    assert ScoreComponents.compute_scanner_bonus("A") == 10.0


def test_scanner_bonus_B():
    assert ScoreComponents.compute_scanner_bonus("B") == 5.0


def test_scanner_bonus_unknown():
    assert ScoreComponents.compute_scanner_bonus("C") == 0.0


# ── Volume Score ─────────────────────────────────────────────


def test_volume_score_spike():
    klines = _make_klines(25)
    klines[-1]["volume"] = 10_000.0  # 큰 급증
    score = SC.compute_volume_score({"klines_3m": klines})
    assert score == 10.0


def test_volume_score_low():
    klines = _make_klines(25)
    klines[-1]["volume"] = 0.1  # 매우 낮음
    score = SC.compute_volume_score({"klines_3m": klines})
    assert score == 2.0


def test_volume_score_insufficient_data():
    score = SC.compute_volume_score({"klines_3m": _make_klines(5)})
    assert score == 2.0


# ── Volatility Score ─────────────────────────────────────────


def test_volatility_score_range():
    score = SC.compute_volatility_score(_state())
    assert 0.0 <= score <= 10.0


def test_volatility_score_on_empty():
    score = SC.compute_volatility_score({})
    assert score == 2.0


# ── Orderflow Score ──────────────────────────────────────────


def test_orderflow_score_max_conf():
    score = ScoreComponents.compute_orderflow_score({"max_confidence": 1.0})
    assert score == 10.0


def test_orderflow_score_zero():
    score = ScoreComponents.compute_orderflow_score({"max_confidence": 0.0})
    assert score == 0.0


def test_orderflow_score_mid():
    score = ScoreComponents.compute_orderflow_score({"max_confidence": 0.5})
    assert abs(score - 5.0) < 0.01


# ── Pattern Quality Score ───────────────────────────────────


def test_pattern_all_layers():
    score = SC.compute_pattern_quality_score({"layer1": True, "layer2": True, "layer3": True})
    assert abs(score - 10.0) < 0.01


def test_pattern_two_layers():
    score = SC.compute_pattern_quality_score({"layer1": True, "layer2": True, "layer3": False})
    assert abs(score - 6.6) < 0.01


def test_pattern_no_layers():
    score = SC.compute_pattern_quality_score({"layer1": False, "layer2": False, "layer3": False})
    assert score == 0.0


# ── Funding Bonus ────────────────────────────────────────────


def test_funding_bonus_short_extreme():
    score = ScoreComponents.compute_funding_bonus(0.002, "SHORT")
    assert score == 8.0


def test_funding_bonus_short_med():
    score = ScoreComponents.compute_funding_bonus(0.0006, "SHORT")
    assert score == 4.0


def test_funding_bonus_long_extreme():
    score = ScoreComponents.compute_funding_bonus(-0.001, "LONG")
    assert score == 8.0


def test_funding_bonus_long_mild():
    score = ScoreComponents.compute_funding_bonus(-0.0003, "LONG")
    assert score == 4.0


def test_funding_bonus_neutral():
    score = ScoreComponents.compute_funding_bonus(0.0001, "LONG")
    assert score == 0.0


def test_funding_bonus_zero():
    score = ScoreComponents.compute_funding_bonus(0.0, "SHORT")
    assert score == 0.0

