from src.execution.order_router import OrderRouter
from src.execution.bracket_order_manager import BracketOrderManager


def _bom():
    router = OrderRouter(paper_mode=True)
    return BracketOrderManager(order_router=router, paper_mode=True)


def test_returns_dict_with_required_keys():
    bom = _bom()
    result = bom.place_bracket(
        "BTCUSDT", "Buy", 1.0,
        entry_price=43000.0, stop_price=42500.0,
        tp1_price=43600.0, tp2_price=44000.0,
        tp1_qty_ratio=0.5,
    )
    assert "tp1" in result
    assert "sl" in result
    assert "tp2_pending" in result


def test_tp2_pending_price_correct():
    bom = _bom()
    result = bom.place_bracket(
        "BTCUSDT", "Buy", 1.0,
        43000.0, 42500.0, 43600.0, 44000.0, 0.5
    )
    assert result["tp2_pending"] == 44000.0


def test_sl_registered_paper_mode():
    assert _bom().verify_sl_registered("BTCUSDT") is True


def test_sl_order_has_stop_price():
    bom = _bom()
    result = bom.place_bracket(
        "BTCUSDT", "Buy", 1.0,
        43000.0, 42500.0, 43600.0, 44000.0, 0.5
    )
    assert result["sl"].get("stop_price") == 42500.0


def test_no_exception_on_zero_qty():
    bom = _bom()
    result = bom.place_bracket(
        "BTCUSDT", "Buy", 0.0,
        43000.0, 42500.0, 43600.0, 44000.0, 0.5
    )
    assert isinstance(result, dict)
