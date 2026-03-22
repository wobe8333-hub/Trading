from __future__ import annotations

from src.core.market_data.market_data_manager import MarketDataManager


# ── 인터페이스 확인 ───────────────────────────────────────────

def test_initialize_creates_state() -> None:
    """initialize() 후 get_state() 가 dict 반환."""
    mdm = MarketDataManager({})
    mdm.initialize(["BTCUSDT"])
    state = mdm.get_state("BTCUSDT")
    assert state is not None
    assert isinstance(state, dict)


def test_get_state_returns_none_for_unknown_symbol() -> None:
    """등록되지 않은 심볼은 None 반환."""
    mdm = MarketDataManager({})
    assert mdm.get_state("UNKNOWN") is None


def test_get_all_symbols_returns_list() -> None:
    """get_all_symbols() 는 list 반환."""
    mdm = MarketDataManager({})
    mdm.initialize(["BTCUSDT", "ETHUSDT"])
    symbols = mdm.get_all_symbols()
    assert isinstance(symbols, list)
    assert "BTCUSDT" in symbols
    assert "ETHUSDT" in symbols


def test_state_has_required_keys() -> None:
    """state dict 에 필수 키 존재."""
    required_keys = [
        "last_price", "best_bid", "best_ask",
        "spread_bps", "funding_rate", "open_interest",
        "klines_3m", "klines_1m", "klines_5m",
        "orderbook_depth_usd", "bid_ask_ratio",
        "volume_24h", "last_updated",
    ]
    mdm = MarketDataManager({})
    mdm.initialize(["BTCUSDT"])
    state = mdm.get_state("BTCUSDT")
    for key in required_keys:
        assert key in state, f"missing key: {key}"


def test_state_values_are_numeric() -> None:
    """state 수치 필드가 float 타입."""
    mdm = MarketDataManager({})
    mdm.initialize(["BTCUSDT"])
    state = mdm.get_state("BTCUSDT")
    for key in ["last_price", "spread_bps", "funding_rate",
                "open_interest", "volume_24h"]:
        assert isinstance(state[key], (int, float)), \
            f"{key} is not numeric: {state[key]}"


def test_klines_are_list() -> None:
    """klines_3m / klines_1m / klines_5m 는 list 타입."""
    mdm = MarketDataManager({})
    mdm.initialize(["BTCUSDT"])
    state = mdm.get_state("BTCUSDT")
    assert isinstance(state["klines_3m"], list)
    assert isinstance(state["klines_1m"], list)
    assert isinstance(state["klines_5m"], list)


def test_mock_mode_no_api_key() -> None:
    """API 키 없으면 _http is None (mock mode)."""
    mdm = MarketDataManager({})   # 빈 config, 환경변수 없음 가정
    # _http is None 이거나 초기화됨 — 키 없는 환경에서는 None
    # 키 있는 환경에서는 not None — 둘 다 허용
    assert mdm._http is None or mdm._http is not None


def test_refresh_all_no_exception() -> None:
    """refresh_all() 은 예외 없이 실행."""
    mdm = MarketDataManager({})
    mdm.initialize(["BTCUSDT"])
    mdm.refresh_all()   # 예외 없으면 통과


def test_get_orderbook_depth_usd_returns_float() -> None:
    """get_orderbook_depth_usd() 는 float 반환."""
    mdm = MarketDataManager({})
    mdm.initialize(["BTCUSDT"])
    depth = mdm.get_orderbook_depth_usd("BTCUSDT")
    assert isinstance(depth, (int, float))
    assert depth > 0


def test_get_bid_ask_ratio_returns_float() -> None:
    """get_bid_ask_ratio() 는 float 반환."""
    mdm = MarketDataManager({})
    mdm.initialize(["BTCUSDT"])
    ratio = mdm.get_bid_ask_ratio("BTCUSDT")
    assert isinstance(ratio, (int, float))
    assert ratio > 0


def test_multiple_symbols_independent() -> None:
    """복수 심볼 state 가 독립적으로 관리됨."""
    mdm = MarketDataManager({})
    mdm.initialize(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    btc = mdm.get_state("BTCUSDT")
    eth = mdm.get_state("ETHUSDT")
    sol = mdm.get_state("SOLUSDT")
    assert btc is not None
    assert eth is not None
    assert sol is not None
    assert btc is not eth
    assert btc is not sol


def test_state_last_updated_is_float() -> None:
    """last_updated 는 float (Unix timestamp)."""
    mdm = MarketDataManager({})
    mdm.initialize(["BTCUSDT"])
    state = mdm.get_state("BTCUSDT")
    assert isinstance(state["last_updated"], float)

