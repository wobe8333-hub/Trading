from src.core.coin_scanner.scanner_state import ScannerState


def _make_top3():
    return [
        {"symbol": "BTCUSDT", "score": 90.0, "grade": "S", "coin_type": "CORE", "features": {}},
        {"symbol": "ETHUSDT", "score": 85.0, "grade": "A", "coin_type": "CORE", "features": {}},
        {"symbol": "SOLUSDT", "score": 75.0, "grade": "B", "coin_type": "HIGH_BETA", "features": {}},
    ]


def setup_function():
    ScannerState.reset()


def test_singleton():
    s1 = ScannerState()
    s2 = ScannerState()
    assert s1 is s2


def test_update_and_get_top3():
    state = ScannerState()
    top3 = _make_top3()
    state.update(top3=top3, full_ranking=top3, coin_types={}, macro_state="BULL")
    result = state.get_top3()
    assert len(result) == 3
    assert result[0]["symbol"] == "BTCUSDT"


def test_is_in_top3():
    state = ScannerState()
    state.update(top3=_make_top3(), full_ranking=[], coin_types={}, macro_state="BULL")
    assert state.is_in_top3("BTCUSDT") is True
    assert state.is_in_top3("XRPUSDT") is False


def test_get_symbol_score():
    state = ScannerState()
    top3 = _make_top3()
    state.update(top3=top3, full_ranking=top3, coin_types={}, macro_state="BULL")
    assert state.get_symbol_score("BTCUSDT") == 90.0
    assert state.get_symbol_score("UNKNOWN") == 0.0


def test_get_coin_type():
    state = ScannerState()
    state.update(
        top3=[], full_ranking=[],
        coin_types={"BTCUSDT": "CORE", "SOLUSDT": "HIGH_BETA"},
        macro_state="NEUTRAL",
    )
    assert state.get_coin_type("BTCUSDT") == "CORE"
    assert state.get_coin_type("UNKNOWN") == "UNKNOWN"


def test_scan_count_increments():
    state = ScannerState()
    state.update(top3=[], full_ranking=[], coin_types={}, macro_state="BULL")
    state.update(top3=[], full_ranking=[], coin_types={}, macro_state="BEAR")
    snap = state.get_snapshot()
    assert snap["scan_count"] == 2


def test_get_snapshot_keys():
    state = ScannerState()
    state.update(top3=_make_top3(), full_ranking=[], coin_types={}, macro_state="BULL")
    snap = state.get_snapshot()
    for key in ["top3", "full_ranking", "last_scan_time", "macro_state_at_scan", "scan_count"]:
        assert key in snap
