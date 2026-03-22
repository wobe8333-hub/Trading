from src.core.coin_scanner.scanner_features import ScannerFeatureCalculator

CALC = ScannerFeatureCalculator()


def _make_state(**overrides):
    """테스트용 최소 market_state 생성."""
    base = {
        "volume_24h":        10_000_000_000.0,
        "spread_bps":        0.02,
        "funding_rate":      0.001,
        "open_interest":     5000.0,
        "oi_prev_5m":        4900.0,
        "bid_ask_ratio":     1.3,
        "orderbook_depth_usd": 800_000.0,
        "recent_trades":     [{"price": 65000, "size": 1, "side": "Buy", "ts_ms": 0}] * 20,
        "klines_3m":         [],
        "klines_1m":         [],
    }
    base.update(overrides)
    return base


def test_returns_all_required_keys():
    state = _make_state()
    result = CALC.compute_all_features("BTCUSDT", state)
    for key in [
        "liquidity_score", "volatility_score", "momentum_score",
        "participation_score", "orderbook_quality",
        "funding_imbalance_score", "event_score", "total_score", "raw",
    ]:
        assert key in result, f"missing key: {key}"


def test_total_score_within_range():
    state = _make_state()
    result = CALC.compute_all_features("BTCUSDT", state)
    assert 0.0 <= result["total_score"] <= 100.0


def test_zero_features_on_empty_state():
    result = CALC.compute_all_features("UNKNOWN", {})
    assert result["total_score"] == 0.0


def test_raw_keys_present():
    state = _make_state()
    result = CALC.compute_all_features("BTCUSDT", state)
    for key in [
        "volume_24h", "spread_bps", "atr_expansion",
        "ema20_slope", "ema50_slope", "vwap_deviation",
        "oi_change_5m_pct", "oi_change_15m_pct",
        "bid_ask_ratio", "funding_rate", "trade_velocity",
    ]:
        assert key in result["raw"], f"missing raw key: {key}"


def test_funding_imbalance_score_tiers():
    # 0.001 → 8점
    r1 = CALC.compute_all_features("X", _make_state(funding_rate=0.001))
    assert r1["funding_imbalance_score"] == 8.0
    # 0.0005 → 5점
    r2 = CALC.compute_all_features("X", _make_state(funding_rate=0.0005))
    assert r2["funding_imbalance_score"] == 5.0
    # 0.0002 → 3점
    r3 = CALC.compute_all_features("X", _make_state(funding_rate=0.0002))
    assert r3["funding_imbalance_score"] == 3.0
    # 0.0001 → 0점
    r4 = CALC.compute_all_features("X", _make_state(funding_rate=0.0001))
    assert r4["funding_imbalance_score"] == 0.0


def test_score_clamped_no_overflow():
    # 모든 수치를 최대로 설정해도 100점 초과 불가
    klines = [
        {"open": 100, "high": 200, "low": 50, "close": 150, "volume": 1e9, "timestamp": i}
        for i in range(100)
    ]
    state = _make_state(
        volume_24h=1e12,
        spread_bps=0.001,
        funding_rate=0.01,
        open_interest=1e6,
        oi_prev_5m=1.0,
        bid_ask_ratio=5.0,
        orderbook_depth_usd=1e9,
        recent_trades=[{"price": 1, "size": 1, "side": "Buy", "ts_ms": i} for i in range(50)],
        klines_3m=klines,
        klines_1m=klines,
    )
    result = CALC.compute_all_features("BTCUSDT", state)
    assert result["total_score"] <= 100.0


def test_no_exception_on_bad_data():
    # 비정상 데이터도 예외 없이 0점 반환
    result = CALC.compute_all_features("BAD", {"volume_24h": None, "spread_bps": "abc"})
    assert result["total_score"] == 0.0
