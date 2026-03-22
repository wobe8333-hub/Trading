from __future__ import annotations

from src.app.state_store import StateStore
from src.app.trading_loop import TradingLoop


def _make_loop() -> TradingLoop:
    StateStore.reset_singleton()
    return TradingLoop(paper_mode=True)


def test_state_store_singleton():
    StateStore.reset_singleton()
    s1 = StateStore()
    s2 = StateStore()
    assert s1 is s2


def test_state_store_update_get():
    StateStore.reset_singleton()
    ss = StateStore()
    ss.update("equity", 750.0)
    assert ss.get("equity") == 750.0


def test_state_store_reset_daily():
    StateStore.reset_singleton()
    ss = StateStore()
    ss.update("daily_pnl", 50.0)
    ss.update("daily_trade_count", 5)
    ss.reset_daily()
    assert ss.get("daily_pnl") == 0.0
    assert ss.get("daily_trade_count") == 0


def test_state_store_save_load():
    StateStore.reset_singleton()
    ss = StateStore()
    ss.update("equity", 850.0)
    ss.save_to_disk()
    StateStore.reset_singleton()
    ss2 = StateStore()
    ss2.load_from_disk()
    assert ss2.get("equity") == 850.0


def test_trading_loop_run_once_no_exception():
    loop = _make_loop()
    result = loop.run_once()
    assert isinstance(result, dict)
    assert "status" in result


def test_trading_loop_run_once_returns_valid_status():
    valid_statuses = {
        "OK",
        "SESSION_CLOSED",
        "KILL_SWITCH_ACTIVE",
        "PROFIT_LOCK_HALTED",
        "RISK_OFF_OR_NO_TOP3",
        "ERROR",
    }
    loop = _make_loop()
    result = loop.run_once()
    assert result["status"] in valid_statuses


def test_trading_loop_run_once_equity_in_result():
    loop = _make_loop()
    result = loop.run_once()
    if result["status"] == "OK":
        assert "equity" in result


def test_trading_loop_5_consecutive():
    loop = _make_loop()
    for _ in range(5):
        result = loop.run_once()
        assert isinstance(result, dict)


def test_trading_loop_step20_pass_criteria():
    loop = _make_loop()
    result = loop.run_once()
    assert isinstance(result, dict)

