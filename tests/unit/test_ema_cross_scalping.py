from src.strategy.strategy_library.ema_cross_scalping import EMACrossScalping


def _cfg():
    return {
        "enabled": True,
        "min_entry_score": 70,
        "min_rr": 1.2,
        "allowed_regimes": ["TREND_UP", "TREND_DOWN", "RANGE"],
        "forbidden_regimes": ["EXPANSION"],
        "preferred_macro": ["NEUTRAL", "BULL", "BEAR"],
        "preferred_coin_types": ["CORE", "RANGE_PLAY", "HIGH_BETA"],
        "params": {"ema_fast": 5, "ema_slow": 20, "volume_ratio_min": 1.0},
    }


def _of():
    return {
        "liquidation": {"confidence": 0.0},
        "stop_hunt": {"confidence": 0.0},
        "imbalance": {"confidence": 0.0},
        "max_confidence": 0.0,
    }


def _klines_up(n=50):
    """상승 추세 klines — EMA5 > EMA20 골든크로스 유도."""
    klines = []
    for i in range(n):
        if i < 30:
            c = 100.0 - (30 - i) * 0.2  # 하락 후
        else:
            c = 94.0 + (i - 30) * 0.5  # 상승 반전
        klines.append(
            {
                "open": c - 0.1,
                "high": c + 0.2,
                "low": c - 0.2,
                "close": c,
                "volume": 1200.0,
            }
        )
    return {"klines_3m": klines}


def _klines_down(n=50):
    """하락 추세 klines — EMA5 < EMA20 데드크로스 유도."""
    klines = []
    for i in range(n):
        if i < 30:
            c = 100.0 + (30 - i) * 0.2
        else:
            c = 106.0 - (i - 30) * 0.5
        klines.append(
            {
                "open": c + 0.1,
                "high": c + 0.2,
                "low": c - 0.2,
                "close": c,
                "volume": 1200.0,
            }
        )
    return {"klines_3m": klines}


def test_returns_tuple():
    strat = EMACrossScalping(_cfg())
    sig, hit = strat.generate_signal("BTCUSDT", _klines_up(), _of())
    assert isinstance(sig, bool)
    assert isinstance(hit, dict)


def test_layer_hit_keys():
    strat = EMACrossScalping(_cfg())
    _, hit = strat.generate_signal("BTCUSDT", {}, _of())
    for k in ("layer1", "layer2", "layer3", "direction"):
        assert k in hit


def test_no_signal_empty_klines():
    strat = EMACrossScalping(_cfg())
    sig, _ = strat.generate_signal("BTCUSDT", {"klines_3m": []}, _of())
    assert sig is False


def test_no_signal_insufficient_klines():
    klines = [{"open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}] * 10
    strat = EMACrossScalping(_cfg())
    sig, _ = strat.generate_signal("BTCUSDT", {"klines_3m": klines}, _of())
    assert sig is False


def test_no_exception_on_none_state():
    strat = EMACrossScalping(_cfg())
    sig, hit = strat.generate_signal("BTCUSDT", {}, _of())
    assert sig is False


def test_is_allowed_range():
    strat = EMACrossScalping(_cfg())
    assert strat.is_allowed("NEUTRAL", "RANGE") is True


def test_is_allowed_trend_up():
    strat = EMACrossScalping(_cfg())
    assert strat.is_allowed("BULL", "TREND_UP") is True


def test_is_allowed_expansion_blocked():
    strat = EMACrossScalping(_cfg())
    assert strat.is_allowed("NEUTRAL", "EXPANSION") is False


def test_is_allowed_risk_off_blocked():
    strat = EMACrossScalping(_cfg())
    assert strat.is_allowed("RISK_OFF", "RANGE") is False


def test_validate_rr_pass():
    strat = EMACrossScalping(_cfg())
    ok, rr = strat.validate_rr(100.0, 99.0, 101.2)
    assert ok is True
    assert rr >= 1.2


def test_validate_rr_fail():
    strat = EMACrossScalping(_cfg())
    ok, _ = strat.validate_rr(100.0, 99.0, 100.5)
    assert ok is False


def test_metadata_keys():
    strat = EMACrossScalping(_cfg())
    meta = strat.metadata()
    for k in ("allowed_regimes", "min_entry_score", "params"):
        assert k in meta


def test_no_signal_low_volume():
    ms = _klines_up()
    ms["klines_3m"][-1]["volume"] = 0.0
    strat = EMACrossScalping(_cfg())
    sig, hit = strat.generate_signal("BTCUSDT", ms, _of())
    assert sig is False
    if hit.get("layer1"):
        assert hit.get("layer2") is False
