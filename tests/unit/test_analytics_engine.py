from src.analytics.analytics_engine import AnalyticsEngine
from src.analytics.expectancy_engine import ExpectancyEngine
from src.analytics.layer_analyzer import LayerAnalyzer
from src.analytics.target_tracker import TargetTracker
from src.analytics.parameter_validator import ParameterValidator


def _make_trade(
    pnl=5.0,
    strategy="vwap_pullback",
    symbol="BTCUSDT",
    regime="TREND_UP",
    r=1.5,
    l1=True,
    l2=True,
    l3=True,
):
    return {
        "timestamp": "2024-01-01T00:00:00Z",
        "symbol": symbol,
        "strategy": strategy,
        "regime": regime,
        "pnl_net": pnl,
        "r_multiple": r,
        "strategy_layer_hit": {"layer1": l1, "layer2": l2, "layer3": l3},
    }


def test_record_and_count():
    eng = AnalyticsEngine()
    eng.record_trade(_make_trade())
    assert eng.get_total_trade_count() == 1


def test_cold_start_flag():
    eng = AnalyticsEngine()
    assert eng.get_cold_start_flag() is True
    for _ in range(50):
        eng.record_trade(_make_trade())
    assert eng.get_cold_start_flag() is False


def test_get_trades_filter_strategy():
    eng = AnalyticsEngine()
    eng.record_trade(_make_trade(strategy="vwap_pullback"))
    eng.record_trade(_make_trade(strategy="trend_continuation"))
    result = eng.get_trades(strategy="vwap_pullback")
    assert len(result) == 1


def test_expectancy_empty():
    ee = ExpectancyEngine()
    r = ee.compute_expectancy([])
    assert r["total_trades"] == 0


def test_expectancy_all_wins():
    ee = ExpectancyEngine()
    trades = [_make_trade(pnl=10.0) for _ in range(5)]
    r = ee.compute_expectancy(trades)
    assert r["win_rate"] == 1.0
    assert r["expectancy"] > 0


def test_expectancy_by_strategy():
    ee = ExpectancyEngine()
    trades = [_make_trade(strategy="vwap_pullback", pnl=5.0)] * 3
    result = ee.compute_by_strategy(trades)
    assert "vwap_pullback" in result


def test_layer_all_pass():
    la = LayerAnalyzer()
    trades = [_make_trade(l1=True, l2=True, l3=True, pnl=5.0)] * 5
    result = la.analyze(trades)
    assert result["layer3_pass_rate"] == 1.0
    assert result["expectancy_by_layer_combo"]["1_2_3"] > 0


def test_layer_empty():
    la = LayerAnalyzer()
    result = la.analyze([])
    assert result["layer1_pass_rate"] == 0.0


def test_target_tracker_on_track():
    tt = TargetTracker()
    trades = [_make_trade(pnl=50.0, r=1.5) for _ in range(10)]
    result = tt.compute(800, 700, 10000, trades, 5.0)
    assert "remaining_amount" in result
    assert result["remaining_amount"] == 9200.0


def test_target_tracker_no_history():
    tt = TargetTracker()
    result = tt.compute(700, 700, 10000, [], 0.0)
    assert result["current_equity"] == 700.0


def test_target_tracker_warning_low_win_rate():
    tt = TargetTracker()
    trades = [_make_trade(pnl=-1.0, r=0.5) for _ in range(20)]
    result = tt.compute(680, 700, 10000, trades, 10.0)
    assert result["warning"] is not None


def test_parameter_validator_insufficient_data():
    pv = ParameterValidator()
    result = pv.validate_strategy_params("vwap_pullback", "vwap_band_pct", 0.0015, [])
    assert "부족" in result["recommendation"]


def test_parameter_validator_with_data():
    pv = ParameterValidator()
    trades = [_make_trade(pnl=5.0) for _ in range(55)]
    result = pv.validate_strategy_params("vwap_pullback", "vwap_band_pct", 0.0015, trades)
    assert "current_value" in result
    assert "best_value" in result
    assert result["recommendation"] in ("교체 권고", "현재 유지")

