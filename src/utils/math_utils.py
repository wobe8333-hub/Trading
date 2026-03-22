from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple


def _safe(val: Any, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def compute_ema(prices: List[float], period: int) -> List[float]:
    """EWM 방식 EMA. pandas ewm(span=period, adjust=False) 동일."""
    if not prices:
        return []
    alpha = 2.0 / (period + 1)
    emas  = [prices[0]]
    for p in prices[1:]:
        emas.append(emas[-1] * (1 - alpha) + p * alpha)
    return emas


def compute_atr(
    highs:  List[float],
    lows:   List[float],
    closes: List[float],
    period: int = 14,
) -> List[float]:
    """True Range 기반 ATR 리스트 반환."""
    if len(highs) < 2:
        return []
    trs: List[float] = []
    for i in range(1, len(highs)):
        h  = _safe(highs[i])
        l  = _safe(lows[i])
        pc = _safe(closes[i - 1])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if not trs:
        return []
    alpha = 1.0 / period
    atrs  = [trs[0]]
    for tr in trs[1:]:
        atrs.append(atrs[-1] * (1 - alpha) + tr * alpha)
    return atrs


def compute_vwap(closes: List[float], volumes: List[float]) -> List[float]:
    """일간 기준 누적 VWAP 리스트 반환."""
    if not closes or not volumes:
        return []
    pv_cum = v_cum = 0.0
    result: List[float] = []
    for c, v in zip(closes, volumes):
        pv_cum += _safe(c) * _safe(v)
        v_cum  += _safe(v)
        result.append(pv_cum / v_cum if v_cum > 0 else _safe(c))
    return result


def compute_support_resistance(
    candles: List[Dict[str, Any]],
    lookback: int = 20,
) -> Tuple[List[float], List[float]]:
    """
    최근 lookback봉 기준 지지/저항 레벨 반환.
    supports:    최근 저점 리스트 (내림차순 정렬)
    resistances: 최근 고점 리스트 (오름차순 정렬)
    """
    recent = candles[-lookback:] if len(candles) >= lookback else candles
    lows   = sorted([_safe(k.get("low"))  for k in recent])
    highs  = sorted([_safe(k.get("high")) for k in recent], reverse=True)
    return lows[:5], highs[:5]


def count_pullback_candles(
    closes: List[float],
    vwap:   List[float],
    direction: str,
) -> int:
    """
    최근 봉에서 VWAP 반대 방향으로 연속 pullback한 봉 수 반환.
    direction="LONG" → 가격이 VWAP 아래로 내려간 봉 카운트
    direction="SHORT" → 가격이 VWAP 위로 올라간 봉 카운트
    """
    count = 0
    for i in range(len(closes) - 1, max(len(closes) - 10, -1), -1):
        if i >= len(vwap):
            continue
        if direction == "LONG" and closes[i] < vwap[i]:
            count += 1
        elif direction == "SHORT" and closes[i] > vwap[i]:
            count += 1
        else:
            break
    return count


def compute_fibonacci_retracement(high: float, low: float) -> Dict[str, float]:
    """
    구현지침서 명세:
    diff = high - low
    return {
      "0.236": high - diff * 0.236,
      "0.382": high - diff * 0.382,
      "0.500": high - diff * 0.500,
      "0.618": high - diff * 0.618,
    }
    """
    diff = _safe(high) - _safe(low)
    return {
        "0.236": high - diff * 0.236,
        "0.382": high - diff * 0.382,
        "0.500": high - diff * 0.500,
        "0.618": high - diff * 0.618,
    }

