from src.growth.position_scaler import PositionScaler

PS = PositionScaler()


# ── compute_position_size ────────────────────────────────────

def test_position_size_formula():
    """
    구현지침서 공식:
    equity=700, risk_pct=0.032, atr=50, regime=TREND_UP, lev=20
    stop_mult=0.8
    risk_usd=700*0.032=22.4
    stop_distance=50*0.8=40
    size=22.4/(40/20)=22.4/2=11.2
    """
    size = PS.compute_position_size(700, 0.032, 50, "TREND_UP")
    assert abs(size - 11.2) < 0.01, f"expected 11.2 got {size}"


def test_position_size_range_smaller():
    """RANGE는 stop_atr_range=0.6으로 더 큰 포지션 사이즈."""
    size_trend = PS.compute_position_size(700, 0.032, 50, "TREND_UP")
    size_range = PS.compute_position_size(700, 0.032, 50, "RANGE")
    # RANGE stop_mult=0.6 < TREND 0.8 → stop_distance 작음 → size 큼
    assert size_range > size_trend


def test_position_size_zero_atr():
    size = PS.compute_position_size(700, 0.032, 0.0, "TREND_UP")
    assert size == 0.0


def test_position_size_positive():
    size = PS.compute_position_size(700, 0.032, 50, "TREND_UP")
    assert size > 0


# ── compute_stop_price ───────────────────────────────────────

def test_stop_price_long_below_entry():
    """TREND_UP LONG: stop_price = 43000 - 50*0.8 = 42960."""
    stop = PS.compute_stop_price(43000, 50, "TREND_UP", "LONG")
    assert stop < 43000
    assert abs(stop - 42960.0) < 0.01


def test_stop_price_short_above_entry():
    stop = PS.compute_stop_price(43000, 50, "TREND_UP", "SHORT")
    assert stop > 43000
    assert abs(stop - 43040.0) < 0.01


def test_stop_price_range_regime():
    """RANGE stop_mult=0.6: 43000 - 50*0.6 = 42970."""
    stop = PS.compute_stop_price(43000, 50, "RANGE", "LONG")
    assert abs(stop - 42970.0) < 0.01


# ── compute_tp_prices ────────────────────────────────────────

def test_tp_prices_long():
    """TREND_UP LONG: tp1=43000+50*1.2=43060, tp2=43000+50*2.0=43100."""
    tp1, tp2 = PS.compute_tp_prices(43000, 50, "TREND_UP", "LONG")
    assert tp1 > 43000
    assert tp2 > tp1
    assert abs(tp1 - 43060.0) < 0.01
    assert abs(tp2 - 43100.0) < 0.01


def test_tp_prices_short():
    tp1, tp2 = PS.compute_tp_prices(43000, 50, "TREND_UP", "SHORT")
    assert tp1 < 43000
    assert tp2 < tp1


def test_tp2_greater_than_tp1_long():
    tp1, tp2 = PS.compute_tp_prices(43000, 100, "RANGE", "LONG")
    assert tp2 > tp1


# ── get_tp1_ratio ────────────────────────────────────────────

def test_tp1_ratio_trend():
    assert PS.get_tp1_ratio("TREND_UP") == 0.5


def test_tp1_ratio_range():
    assert PS.get_tp1_ratio("RANGE") == 0.6


def test_tp1_ratio_expansion():
    assert PS.get_tp1_ratio("EXPANSION") == 0.4


# ── get_stop_atr_multiplier ──────────────────────────────────

def test_stop_atr_trend():
    assert abs(PS.get_stop_atr_multiplier("TREND_UP") - 0.8) < 0.001


def test_stop_atr_range():
    assert abs(PS.get_stop_atr_multiplier("RANGE") - 0.6) < 0.001


def test_stop_atr_expansion():
    assert abs(PS.get_stop_atr_multiplier("EXPANSION") - 0.9) < 0.001

