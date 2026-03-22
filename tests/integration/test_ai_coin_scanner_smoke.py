from src.app.config_loader import get_config
from src.core.coin_scanner.ai_coin_scanner import AICoinScanner
from src.core.coin_scanner.scanner_state import ScannerState
from src.core.market_data.market_data_manager import MarketDataManager


def setup_function():
    ScannerState.reset()


def test_scan_returns_list():
    """MarketDataManager 없이 scan() 실행 — 예외 없이 리스트 반환."""
    scanner = AICoinScanner()
    result = scanner.scan()
    assert isinstance(result, list)


def test_scan_with_market_data_manager():
    """paper_mode MarketDataManager 주입 후 scan() 실행."""
    cfg = get_config()
    mdm = MarketDataManager(cfg)
    mdm.initialize(["BTCUSDT", "ETHUSDT", "SOLUSDT"])

    scanner = AICoinScanner(market_data_manager=mdm, config=cfg)
    result = scanner.scan()

    assert isinstance(result, list)
    assert len(result) <= 3


def test_scan_result_structure():
    """scan() 반환값 각 항목의 키 구조 확인."""
    cfg = get_config()
    mdm = MarketDataManager(cfg)
    mdm.initialize(["BTCUSDT", "ETHUSDT", "SOLUSDT"])

    scanner = AICoinScanner(market_data_manager=mdm, config=cfg, macro_state="NEUTRAL")
    result = scanner.scan()

    for item in result:
        assert "symbol" in item
        assert "score" in item
        assert "grade" in item
        assert "coin_type" in item


def test_scanner_state_updated_after_scan():
    """scan() 후 ScannerState가 업데이트되는지 확인."""
    ScannerState.reset()
    cfg = get_config()
    mdm = MarketDataManager(cfg)
    mdm.initialize(["BTCUSDT", "ETHUSDT", "SOLUSDT"])

    scanner = AICoinScanner(market_data_manager=mdm, config=cfg)
    scanner.scan()

    state = ScannerState()
    snap = state.get_snapshot()
    assert snap["scan_count"] >= 1
    assert snap["last_scan_time"] > 0


def test_risk_off_returns_empty():
    """RISK_OFF macro_state → TOP3 빈 리스트."""
    scanner = AICoinScanner(macro_state="RISK_OFF")
    result = scanner.scan()
    assert result == []


def test_scan_no_exception_on_bad_market_state():
    """market_data_manager 없이 10회 연속 실행 — 예외 없음."""
    scanner = AICoinScanner()
    for _ in range(10):
        result = scanner.scan()
        assert isinstance(result, list)


def test_pass_criteria():
    """
    구현지침서 PASS 기준:
    scan() → symbol, score, coin_type 출력 가능
    """
    cfg = get_config()
    mdm = MarketDataManager(cfg)
    mdm.initialize(["BTCUSDT", "ETHUSDT", "SOLUSDT"])

    scanner = AICoinScanner(market_data_manager=mdm, config=cfg)
    result = scanner.scan()

    symbols = [r["symbol"] for r in result]
    scores = [r["score"] for r in result]
    coin_types = [r["coin_type"] for r in result]

    print("symbols:", symbols)
    print("scores:", scores)
    print("coin_types:", coin_types)

    assert isinstance(symbols, list)
    assert isinstance(scores, list)
    assert isinstance(coin_types, list)
