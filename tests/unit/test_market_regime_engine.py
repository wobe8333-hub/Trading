from src.core.regime_engine.market_regime_engine import (
    MarketRegimeEngine,
    _detect_hh_hl,
    _detect_ll_lh,
    _compute_ema,
    _compute_atr,
    _compute_vwap,
)

ENGINE = MarketRegimeEngine()
_VALID = {"TREND_UP", "TREND_DOWN", "RANGE", "EXPANSION"}


def _make_klines(
    n: int,
    base: float = 100.0,
    direction: str = "flat",
    vol: float = 500.0,
) -> list:
    """테스트용 klines 생성. direction: 'up' / 'down' / 'flat'."""
    klines = []
    for i in range(n):
        if direction == "up":
            c = base + i * 0.5
        elif direction == "down":
            c = base - i * 0.5
        else:
            c = base + (0.1 if i % 2 == 0 else -0.1)
        klines.append({
            "timestamp": i,
            "open":   c - 0.1,
            "high":   c + 0.3,
            "low":    c - 0.3,
            "close":  c,
            "volume": vol,
        })
    return klines


def _make_state(klines: list, price_offset: float = 0.0) -> dict:
    last_close = klines[-1]["close"] if klines else 100.0
    return {
        "klines_3m":  klines,
        "last_price": last_close + price_offset,
        "open_interest": 5000.0,
        "oi_prev_5m": 5000.0,
    }


def test_returns_valid_regime_on_empty_state():
    result = ENGINE.get_regime("BTCUSDT", {})
    assert result in _VALID


def test_always_returns_string():
    for _ in range(5):
        r = ENGINE.get_regime("BTCUSDT", {})
        assert isinstance(r, str) and r in _VALID


def test_empty_klines_returns_range():
    result = ENGINE.get_regime("BTCUSDT", {"klines_3m": []})
    assert result == "RANGE"


def test_flat_market_returns_range():
    """횡보 klines → RANGE."""
    klines = _make_klines(60, direction="flat")
    result = ENGINE.get_regime("BTCUSDT", _make_state(klines))
    assert result == "RANGE"


def test_expansion_detected_on_atr_spike():
    klines = _make_klines(30, direction="flat", vol=100.0)
    klines[-1]["high"]   = klines[-1]["close"] + 50.0
    klines[-1]["low"]    = klines[-1]["close"] - 50.0
    klines[-1]["volume"] = 100_000.0
    result = ENGINE.get_regime("BTCUSDT", _make_state(klines))
    assert result == "EXPANSION"


def test_trend_up_on_rising_klines():
    klines = _make_klines(100, direction="up")
    result = ENGINE.get_regime("BTCUSDT", _make_state(klines, price_offset=20.0))
    assert result == "TREND_UP"


def test_trend_down_on_falling_klines():
    klines = _make_klines(100, direction="down")
    result = ENGINE.get_regime("BTCUSDT", _make_state(klines, price_offset=-20.0))
    assert result == "TREND_DOWN"


def test_expansion_overrides_trend():
    klines = _make_klines(30, direction="up", vol=100.0)
    klines[-1]["high"]   = klines[-1]["close"] + 100.0
    klines[-1]["low"]    = klines[-1]["close"] - 100.0
    klines[-1]["volume"] = 500_000.0
    result = ENGINE.get_regime("BTCUSDT", _make_state(klines, price_offset=10.0))
    assert result == "EXPANSION"


def test_regimes_dict_updated():
    """get_regime 호출 후 self.regimes에 심볼 저장 확인."""
    eng = MarketRegimeEngine()
    eng.get_regime("SOLUSDT", {})
    assert "SOLUSDT" in eng.regimes
    assert eng.regimes["SOLUSDT"] in _VALID


def test_get_all_regimes_returns_dict():
    eng = MarketRegimeEngine()
    eng.get_regime("BTCUSDT", {})
    eng.get_regime("ETHUSDT", {})
    all_r = eng.get_all_regimes()
    assert isinstance(all_r, dict)
    assert "BTCUSDT" in all_r
    assert "ETHUSDT" in all_r


def test_symbols_independent():
    """두 심볼이 서로 다른 Regime으로 저장될 수 있다."""
    eng = MarketRegimeEngine()
    rising_klines  = _make_klines(100, direction="up")
    falling_klines = _make_klines(100, direction="down")
    eng.get_regime("BTCUSDT", _make_state(rising_klines,  price_offset=20.0))
    eng.get_regime("ETHUSDT", _make_state(falling_klines, price_offset=-20.0))
    assert eng.regimes["BTCUSDT"] in _VALID
    assert eng.regimes["ETHUSDT"] in _VALID


def test_no_conflict_on_same_symbol_update():
    """동일 심볼을 여러 번 호출해도 충돌 없이 마지막 값만 저장."""
    eng = MarketRegimeEngine()
    for _ in range(5):
        r = eng.get_regime("BTCUSDT", {})
        assert r in _VALID
    assert eng.regimes["BTCUSDT"] in _VALID


def test_detect_hh_hl_true():
    """단조 상승 → HH, HL 모두 충족."""
    highs = [100 + i for i in range(10)]
    lows  = [99  + i for i in range(10)]
    assert _detect_hh_hl(highs, lows) is True


def test_detect_hh_hl_false_on_flat():
    """횡보 → HH/HL 불충분."""
    highs = [100.0] * 10
    lows  = [99.0]  * 10
    assert _detect_hh_hl(highs, lows) is False


def test_detect_ll_lh_true():
    """단조 하락 → LL, LH 모두 충족."""
    highs = [100 - i for i in range(10)]
    lows  = [99  - i for i in range(10)]
    assert _detect_ll_lh(highs, lows) is True


def test_detect_ll_lh_false_on_flat():
    highs = [100.0] * 10
    lows  = [99.0]  * 10
    assert _detect_ll_lh(highs, lows) is False


def test_compute_ema_length_matches_closes():
    closes = [float(i) for i in range(1, 21)]
    emas   = _compute_ema(closes, 20)
    assert len(emas) == len(closes)


def test_compute_ema_empty_input():
    assert _compute_ema([], 20) == []


def test_compute_atr_empty_klines():
    assert _compute_atr([]) == []


def test_compute_vwap_empty_klines():
    assert _compute_vwap([]) == 0.0


def test_compute_vwap_positive():
    klines = _make_klines(10)
    vwap   = _compute_vwap(klines)
    assert vwap > 0


def test_no_exception_on_none_state():
    result = ENGINE.get_regime("BTCUSDT", None)  # type: ignore
    assert result in _VALID


def test_no_exception_on_bad_klines():
    result = ENGINE.get_regime("BTCUSDT", {"klines_3m": "bad"})
    assert result in _VALID


def test_20_consecutive_no_exception():
    for _ in range(20):
        r = ENGINE.get_regime("BTCUSDT", {})
        assert r in _VALID
