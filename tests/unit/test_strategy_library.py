from src.utils.config_loader import load_strategy_config
from src.strategy.strategy_library.vwap_pullback import VWAPPullback
from src.strategy.strategy_library.trend_continuation import TrendContinuation
from src.strategy.strategy_library.liquidity_sweep_reversal import LiquiditySweepReversal
from src.strategy.strategy_library.breakout_momentum import BreakoutMomentum
from src.strategy.strategy_library.liquidation_scalping import LiquidationScalping
from src.strategy.strategy_library.stop_hunt_reversal import StopHuntReversal
from src.strategy.strategy_library.ema_cross_scalping import EMACrossScalping


def _get_cfg(name: str) -> dict:
    return load_strategy_config()[name]


def _make_klines(n: int, close: float = 100.0) -> list:
    klines = []
    for i in range(n):
        c = close + i * 0.1
        klines.append({
            "timestamp": i,
            "open": c - 0.05,
            "high": c + 0.3,
            "low": c - 0.3,
            "close": c,
            "volume": 1000.0 + i,
        })
    return klines


def _mock_state(n: int = 100):
    klines = _make_klines(n)
    return {
        "klines_3m": klines,
        "klines_1m": _make_klines(n),
        "last_price": klines[-1]["close"],
        "open_interest": 5000.0,
        "oi_prev_5m": 5000.0,
        "bid_ask_ratio": 1.3,
        "orderbook_depth_usd": 500_000.0,
        "recent_trades": [],
    }


def _mock_orderflow():
    return {
        "liquidation": {"event_type": None, "confidence": 0.0},
        "stop_hunt": {"detected": False, "confidence": 0.0, "direction": "NONE"},
        "imbalance": {"event_type": None, "confidence": 0.0},
        "max_confidence": 0.0,
    }


_STRATEGIES = [
    ("vwap_pullback", VWAPPullback),
    ("trend_continuation", TrendContinuation),
    ("liquidity_sweep_reversal", LiquiditySweepReversal),
    ("breakout_momentum", BreakoutMomentum),
    ("liquidation_scalping", LiquidationScalping),
    ("stop_hunt_reversal", StopHuntReversal),
    ("ema_cross_scalping", EMACrossScalping),
]


def test_all_strategies_instantiate():
    cfg = load_strategy_config()
    for name, cls in _STRATEGIES:
        strat = cls(cfg[name])
        assert strat is not None


def test_all_strategies_return_tuple():
    cfg = load_strategy_config()
    state = _mock_state()
    of = _mock_orderflow()
    for name, cls in _STRATEGIES:
        strat = cls(cfg[name])
        result = strat.generate_signal("BTCUSDT", state, of)
        assert isinstance(result, tuple), f"{name}: not a tuple"
        assert len(result) == 2, f"{name}: tuple length != 2"


def test_all_strategies_return_bool_and_dict():
    cfg = load_strategy_config()
    state = _mock_state()
    of = _mock_orderflow()
    for name, cls in _STRATEGIES:
        strat = cls(cfg[name])
        signal, layers = strat.generate_signal("BTCUSDT", state, of)
        assert isinstance(signal, bool), f"{name}: signal not bool"
        assert isinstance(layers, dict), f"{name}: layers not dict"


def test_layer_hit_has_required_keys():
    cfg = load_strategy_config()
    state = _mock_state()
    of = _mock_orderflow()
    for name, cls in _STRATEGIES:
        strat = cls(cfg[name])
        _, layers = strat.generate_signal("BTCUSDT", state, of)
        for k in ["layer1", "layer2", "layer3", "direction"]:
            assert k in layers, f"{name}: missing key {k}"


def test_no_signal_on_empty_klines():
    cfg = load_strategy_config()
    of = _mock_orderflow()
    for name, cls in _STRATEGIES:
        strat = cls(cfg[name])
        signal, _ = strat.generate_signal("BTCUSDT", {"klines_3m": []}, of)
        assert signal is False, f"{name}: should return False on empty klines"


def test_no_exception_on_none_state():
    cfg = load_strategy_config()
    of = _mock_orderflow()
    for name, cls in _STRATEGIES:
        strat = cls(cfg[name])
        signal, _ = strat.generate_signal("BTCUSDT", {}, of)
        assert signal is False


def test_vwap_pullback_validate_rr():
    cfg = _get_cfg("vwap_pullback")
    strat = VWAPPullback(cfg)
    ok, rr = strat.validate_rr(43000, 42500, 43600)
    assert isinstance(ok, bool)
    assert isinstance(rr, float)
    print(f"validate_rr ok={ok} rr={rr}")


def test_is_allowed_all_strategies():
    cfg = load_strategy_config()
    for name, cls in _STRATEGIES:
        strat = cls(cfg[name])
        assert strat.is_allowed("RISK_OFF", "TREND_UP") is False


def test_metadata_all_strategies():
    cfg = load_strategy_config()
    for name, cls in _STRATEGIES:
        strat = cls(cfg[name])
        meta = strat.metadata()
        assert "name" in meta
        assert "allowed_regimes" in meta
        assert "min_rr" in meta

