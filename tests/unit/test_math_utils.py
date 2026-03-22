from src.utils.math_utils import (
    compute_ema,
    compute_atr,
    compute_vwap,
    compute_support_resistance,
    count_pullback_candles,
    compute_fibonacci_retracement,
)


def _klines(n=20, base=100.0):
    return [
        {"timestamp": i, "open": base + i * 0.1, "high": base + i * 0.1 + 0.3,
         "low": base + i * 0.1 - 0.3, "close": base + i * 0.1, "volume": 1000.0}
        for i in range(n)
    ]


def test_compute_ema_length():
    prices = [float(i) for i in range(1, 21)]
    emas = compute_ema(prices, 20)
    assert len(emas) == len(prices)


def test_compute_ema_empty():
    assert compute_ema([], 20) == []


def test_compute_ema_trend():
    rising = [float(i) for i in range(1, 51)]
    emas = compute_ema(rising, 20)
    assert emas[-1] > emas[0]


def test_compute_atr_positive():
    kl = _klines(20)
    h = [k["high"] for k in kl]
    l = [k["low"] for k in kl]
    c = [k["close"] for k in kl]
    atrs = compute_atr(h, l, c, 14)
    assert len(atrs) > 0
    assert all(a >= 0 for a in atrs)


def test_compute_atr_empty():
    assert compute_atr([], [], [], 14) == []


def test_compute_vwap_length():
    kl = _klines(10)
    c = [k["close"] for k in kl]
    v = [k["volume"] for k in kl]
    vw = compute_vwap(c, v)
    assert len(vw) == len(c)


def test_compute_vwap_positive():
    kl = _klines(10, base=100.0)
    c = [k["close"] for k in kl]
    v = [k["volume"] for k in kl]
    vw = compute_vwap(c, v)
    assert all(x > 0 for x in vw)


def test_compute_support_resistance_returns_lists():
    kl = _klines(25)
    supports, resistances = compute_support_resistance(kl, 20)
    assert isinstance(supports, list)
    assert isinstance(resistances, list)


def test_count_pullback_long():
    closes = [101.0, 100.5, 99.8, 99.5, 100.2]
    vwap = [100.0] * 5
    count = count_pullback_candles(closes, vwap, "LONG")
    assert isinstance(count, int)
    assert count >= 0


def test_fibonacci_keys():
    fib = compute_fibonacci_retracement(110.0, 100.0)
    for k in ["0.236", "0.382", "0.500", "0.618"]:
        assert k in fib


def test_fibonacci_values_between_low_high():
    fib = compute_fibonacci_retracement(110.0, 100.0)
    for v in fib.values():
        assert 100.0 <= v <= 110.0

