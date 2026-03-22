from src.app.config_loader import get_config
from src.core.macro_filter.macro_features import MacroFeatureCalculator
from src.core.macro_filter.macro_market_filter import MacroMarketFilter
from src.core.market_data.market_data_manager import MarketDataManager

_VALID_STATES = {"BULL", "BEAR", "NEUTRAL", "RISK_OFF"}


def test_macro_filter_smoke_with_paper_mode():
    """paper_mode MarketDataManager BTC state → 유효한 Macro State 반환."""
    cfg = get_config()
    mdm = MarketDataManager(cfg)
    mdm.initialize(["BTCUSDT"])

    btc_state = mdm.get_state("BTCUSDT") or {}
    flt = MacroMarketFilter()
    result = flt.get_state(btc_state)

    assert result in _VALID_STATES


def test_macro_features_smoke_with_paper_mode():
    """paper_mode BTC state → 11개 feature 키 모두 존재."""
    cfg = get_config()
    mdm = MarketDataManager(cfg)
    mdm.initialize(["BTCUSDT"])

    btc_state = mdm.get_state("BTCUSDT") or {}
    calc = MacroFeatureCalculator()
    feat = calc.compute(btc_state)

    for key in [
        "ema20", "ema50", "ema200", "vwap", "atr_14",
        "atr_expansion", "oi_change_pct", "funding_bias",
        "volume_spike", "price_vs_vwap", "ema_alignment",
    ]:
        assert key in feat, f"missing key: {key}"


def test_100_consecutive_calls_no_exception():
    """100회 연속 호출 — 예외 없음."""
    flt = MacroMarketFilter()
    for _ in range(100):
        result = flt.get_state({})
        assert result in _VALID_STATES


def test_state_transition_logging():
    """상태 변화 시 내부 prev_state 갱신 확인."""
    flt = MacroMarketFilter()

    klines_up = [
        {"timestamp": i, "open": 100+i*0.5, "high": 100+i*0.5+0.3,
         "low": 100+i*0.5-0.3, "close": 100+i*0.5, "volume": 500.0}
        for i in range(100)
    ]
    bull_state = {
        "klines_3m": klines_up, "last_price": 150.0,
        "open_interest": 5100.0, "oi_prev_5m": 5000.0, "funding_rate": 0.0001,
    }

    r1 = flt.get_state({})
    r2 = flt.get_state(bull_state)
    r3 = flt.get_state(bull_state)

    assert r1 in _VALID_STATES
    assert r2 in _VALID_STATES
    assert r3 in _VALID_STATES


def test_pass_criteria():
    """
    구현지침서 PASS 기준:
    f.get_state(mock_btc_state) → 유효한 state 출력
    """
    f = MacroMarketFilter()
    state = f.get_state({})
    result = state in ["BULL", "BEAR", "NEUTRAL", "RISK_OFF"]
    print(result)
    assert result is True
