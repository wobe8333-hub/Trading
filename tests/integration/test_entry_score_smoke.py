from src.app.config_loader import get_config
from src.core.market_data.market_data_manager import MarketDataManager
from src.strategy.entry_score.entry_score_engine import EntryScoreEngine

ENG = EntryScoreEngine()

_VALID_QUALITY = {"A+", "A", "B", "REJECT"}
_VALID_SCALE = {0.0, 0.4, 0.7, 1.0}


def _of():
    return {
        "liquidation": {"confidence": 0.0},
        "stop_hunt": {"confidence": 0.0},
        "imbalance": {"confidence": 0.0},
        "max_confidence": 0.0,
    }


def _layer(all_true=False):
    return {"layer1": all_true, "layer2": all_true, "layer3": all_true}


def test_pass_criteria():
    cfg = get_config()
    mdm = MarketDataManager(cfg)
    mdm.initialize(["BTCUSDT"])
    btc = mdm.get_state("BTCUSDT") or {}

    result = ENG.compute(
        symbol="BTCUSDT",
        strategy_name="vwap_pullback",
        direction="LONG",
        regime="TREND_UP",
        scanner_grade="A",
        market_state=btc,
        orderflow_state=_of(),
        layer_hit=_layer(all_true=True),
        funding_rate=0.0001,
    )
    assert 0.0 <= result["total_score"] <= 100.0
    assert result["position_scale"] in _VALID_SCALE


def test_all_7_strategies_smoke():
    strategies = [
        "vwap_pullback",
        "trend_continuation",
        "liquidity_sweep_reversal",
        "breakout_momentum",
        "liquidation_scalping",
        "stop_hunt_reversal",
        "ema_cross_scalping",
    ]
    cfg = get_config()
    mdm = MarketDataManager(cfg)
    mdm.initialize(["BTCUSDT"])
    btc = mdm.get_state("BTCUSDT") or {}

    for strat in strategies:
        for direction in ["LONG", "SHORT"]:
            result = ENG.compute(
                "BTCUSDT",
                strat,
                direction,
                "TREND_UP",
                "A",
                btc,
                _of(),
                _layer(),
                0.0001,
            )
            assert 0.0 <= result["total_score"] <= 100.0
            assert result["entry_quality"] in _VALID_QUALITY


def test_funding_bonus_cap():
    for _ in range(20):
        result = ENG.compute(
            "BTCUSDT",
            "vwap_pullback",
            "SHORT",
            "TREND_UP",
            "S",
            {},
            {"max_confidence": 1.0},
            {"layer1": True, "layer2": True, "layer3": True},
            0.005,
        )
        assert result["total_score"] <= 100.0


def test_100_consecutive_no_exception():
    for _ in range(100):
        result = ENG.compute(
            "BTCUSDT",
            "vwap_pullback",
            "LONG",
            "TREND_UP",
            "A",
            {},
            _of(),
            _layer(),
            0.0001,
        )
        assert isinstance(result["total_score"], float)

