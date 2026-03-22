from src.utils.config_loader import load_strategy_config
from src.strategy.strategy_library.vwap_pullback import VWAPPullback
from src.strategy.strategy_library.trend_continuation import TrendContinuation
from src.strategy.strategy_library.liquidity_sweep_reversal import LiquiditySweepReversal
from src.strategy.strategy_library.breakout_momentum import BreakoutMomentum
from src.strategy.strategy_library.liquidation_scalping import LiquidationScalping
from src.strategy.strategy_library.stop_hunt_reversal import StopHuntReversal
from src.strategy.strategy_library.ema_cross_scalping import EMACrossScalping
from src.app.config_loader import get_config
from src.core.market_data.market_data_manager import MarketDataManager


def _mock_orderflow():
    return {
        "liquidation": {"event_type": None, "confidence": 0.0},
        "stop_hunt": {"detected": False, "confidence": 0.0, "direction": "NONE"},
        "imbalance": {"event_type": None, "confidence": 0.0},
        "max_confidence": 0.0,
    }


def test_all_7_strategies_with_paper_mode():
    """paper_mode MarketDataManager 연동 — 7개 전략 모두 예외 없이 실행."""
    cfg_sys = get_config()
    mdm = MarketDataManager(cfg_sys)
    mdm.initialize(["BTCUSDT"])
    btc_state = mdm.get_state("BTCUSDT") or {}

    cfg = load_strategy_config()
    of = _mock_orderflow()

    strategies = [
        VWAPPullback(cfg["vwap_pullback"]),
        TrendContinuation(cfg["trend_continuation"]),
        LiquiditySweepReversal(cfg["liquidity_sweep_reversal"]),
        BreakoutMomentum(cfg["breakout_momentum"]),
        LiquidationScalping(cfg["liquidation_scalping"]),
        StopHuntReversal(cfg["stop_hunt_reversal"]),
        EMACrossScalping(cfg["ema_cross_scalping"]),
    ]
    for strat in strategies:
        signal, layers = strat.generate_signal("BTCUSDT", btc_state, of)
        assert isinstance(signal, bool)
        assert isinstance(layers, dict)
        for k in ["layer1", "layer2", "layer3", "direction"]:
            assert k in layers


def test_pass_criteria():
    """
    구현지침서 공식 PASS 기준:
    strat.generate_signal(symbol, mock_state, mock_orderflow) → (signal, layers)
    strat.validate_rr(43000, 42500, 43600) → (bool, rr)
    """
    cfg = load_strategy_config()
    strat = VWAPPullback(cfg["vwap_pullback"])
    of = _mock_orderflow()

    signal, layers = strat.generate_signal("BTCUSDT", {}, of)
    print(signal, layers)
    assert isinstance(signal, bool)

    ok, rr = strat.validate_rr(43000, 42500, 43600)
    print(ok, rr)
    assert isinstance(ok, bool)
    assert isinstance(rr, float)
    print("PASS: strategy library pass criteria")

