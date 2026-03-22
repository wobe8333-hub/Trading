from src.strategy.strategy_library.base_strategy import BaseStrategy

_CFG = {
    "allowed_regimes": ["TREND_UP", "TREND_DOWN", "RANGE"],
    "forbidden_regimes": ["EXPANSION"],
    "preferred_macro": ["BULL", "NEUTRAL"],
    "preferred_coin_types": ["CORE"],
    "min_entry_score": 72,
    "min_rr": 1.2,
    "params": {},
}


class ConcreteStrategy(BaseStrategy):
    def generate_signal(self, symbol, market_state, orderflow_state, direction=None):
        return False, self._null_hit()


STRAT = ConcreteStrategy(_CFG)


def test_allowed_valid_regime():
    assert STRAT.is_allowed("BULL", "TREND_UP") is True


def test_blocked_forbidden_regime():
    assert STRAT.is_allowed("BULL", "EXPANSION") is False


def test_blocked_regime_not_in_allowed():
    assert STRAT.is_allowed("BULL", "UNKNOWN") is False


def test_blocked_risk_off():
    assert STRAT.is_allowed("RISK_OFF", "TREND_UP") is False


def test_validate_rr_pass():
    ok, rr = STRAT.validate_rr(43000, 42500, 43600)
    assert ok is True
    assert abs(rr - 1.2) < 0.01


def test_validate_rr_fail():
    ok, rr = STRAT.validate_rr(43000, 42900, 43050)
    assert ok is False


def test_validate_rr_zero_risk():
    ok, rr = STRAT.validate_rr(43000, 43000, 43600)
    assert ok is False
    assert rr == 0.0


def test_compute_stop_long():
    stop = STRAT.compute_stop(43000, 100, "TREND_UP", "LONG")
    assert stop < 43000


def test_compute_stop_short():
    stop = STRAT.compute_stop(43000, 100, "TREND_UP", "SHORT")
    assert stop > 43000


def test_compute_targets_long():
    tp1, tp2 = STRAT.compute_targets(43000, 100, "TREND_UP", "LONG")
    assert tp1 > 43000
    assert tp2 > tp1


def test_compute_targets_short():
    tp1, tp2 = STRAT.compute_targets(43000, 100, "TREND_UP", "SHORT")
    assert tp1 < 43000
    assert tp2 < tp1


def test_metadata_keys():
    meta = STRAT.metadata()
    for k in ["name", "allowed_regimes", "forbidden_regimes", "min_entry_score", "min_rr", "params"]:
        assert k in meta


def test_tp1_close_ratio_range():
    for regime in ["TREND_UP", "TREND_DOWN", "RANGE", "EXPANSION"]:
        r = STRAT.get_tp1_close_ratio(regime)
        assert 0.0 < r <= 1.0

