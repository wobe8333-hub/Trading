from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

logger = logging.getLogger("orderflow.stop_hunt")

# ── 감지 임계값 ───────────────────────────────────────────────
_WICK_BODY_RATIO_MIN    = 2.0    # [초기값] 꼬리 길이 >= 몸통의 2배
_WICK_ATR_RATIO_MIN     = 0.5    # [검증값] 꼬리 길이 >= ATR * 0.5
_RECOVERY_MAX_CANDLES   = 3      # [초기값] 1~3봉 이내 회복
_SUPPORT_LOOKBACK       = 10     # [초기값] 지지선 계산 최근 10봉


def _safe(val: Any, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _compute_atr_last(klines: List[Dict[str, Any]], period: int = 14) -> float:
    if len(klines) < 2:
        return 0.0
    trs: List[float] = []
    for i in range(1, len(klines)):
        h  = _safe(klines[i].get("high"))
        l  = _safe(klines[i].get("low"))
        pc = _safe(klines[i - 1].get("close"))
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if not trs:
        return 0.0
    alpha = 1.0 / period
    atr   = trs[0]
    for tr in trs[1:]:
        atr = atr * (1 - alpha) + tr * alpha
    return atr


class StopHuntDetector:
    """
    Stop Hunt 패턴 감지기.
    """

    def detect(
        self,
        symbol:       str,
        market_state: Dict[str, Any],
        features:     Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            return self._detect(symbol, market_state, features)
        except Exception as exc:
            logger.error(
                "stop_hunt_detector detect failed symbol=%s error=%s",
                symbol, exc,
            )
            return self._null_result()

    def _detect(
        self,
        symbol:       str,
        market_state: Dict[str, Any],
        features:     Dict[str, Any],
    ) -> Dict[str, Any]:
        klines: List[Dict[str, Any]] = market_state.get("klines_3m") or []
        if len(klines) < _SUPPORT_LOOKBACK + 2:
            return self._null_result()

        recent = klines[-(_SUPPORT_LOOKBACK + 2):]
        atr    = _compute_atr_last(recent, period=14)
        if atr < 1e-9:
            return self._null_result()

        # 지지선 = 최근 lookback봉 최저가, 저항선 = 최고가
        support    = min(_safe(k.get("low"))  for k in recent[:-2])
        resistance = max(_safe(k.get("high")) for k in recent[:-2])

        last   = recent[-1]
        l_open  = _safe(last.get("open"))
        l_high  = _safe(last.get("high"))
        l_low   = _safe(last.get("low"))
        l_close = _safe(last.get("close"))

        body = abs(l_close - l_open)
        lower_wick = l_open - l_low   if l_close >= l_open else l_close - l_low
        upper_wick = l_high - l_open  if l_close >= l_open else l_high - l_close
        lower_wick = max(lower_wick, 0.0)
        upper_wick = max(upper_wick, 0.0)

        oi_change       = float(features.get("oi_change_5m_pct",    0.0))
        bid_depth_chg   = float(features.get("bid_depth_change_pct", 0.0))

        # ── BULL_HUNT 감지 ────────────────────────────────────
        bull_detected = False
        hunt_low: Optional[float] = None

        if (
            l_low < support
            and lower_wick >= body * _WICK_BODY_RATIO_MIN
            and lower_wick >= atr * _WICK_ATR_RATIO_MIN
            and l_close > support
        ):
            bull_detected = True
            hunt_low = l_low

        # ── BEAR_HUNT 감지 ────────────────────────────────────
        bear_detected = False
        hunt_high: Optional[float] = None

        if (
            l_high > resistance
            and upper_wick >= body * _WICK_BODY_RATIO_MIN
            and upper_wick >= atr * _WICK_ATR_RATIO_MIN
            and l_close < resistance
        ):
            bear_detected = True
            hunt_high = l_high

        if not (bull_detected or bear_detected):
            return self._null_result()

        direction = "BULL_HUNT" if bull_detected else "BEAR_HUNT"
        wick_used = lower_wick if bull_detected else upper_wick
        wick_body_ratio = (wick_used / body) if body > 1e-9 else 0.0

        confidence = self._compute_confidence(
            wick_body_ratio, oi_change, bid_depth_chg, recovery_candles=1
        )

        logger.info(
            "stop_hunt_detector event=%s symbol=%s confidence=%.2f",
            direction, symbol, confidence,
        )

        return {
            "detected":   True,
            "direction":  direction,
            "confidence": round(confidence, 4),
            "hunt_low":   hunt_low,
            "hunt_high":  hunt_high,
        }

    @staticmethod
    def _compute_confidence(
        wick_body_ratio:  float,
        oi_change:        float,
        bid_depth_change: float,
        recovery_candles: int,
    ) -> float:
        """
        구현지침서 명세:
          base = 0.4
          if wick_body_ratio > 3.0:   base += 0.15
          if oi_change < -0.01:       base += 0.15
          if bid_depth_change > 0.3:  base += 0.10
          if recovery_candles == 1:   base += 0.10
          elif recovery_candles <= 3: base += 0.05
          return min(base, 1.0)
        """
        base = 0.4
        if wick_body_ratio > 3.0:
            base += 0.15
        if oi_change < -0.01:
            base += 0.15
        if bid_depth_change > 0.3:
            base += 0.10
        if recovery_candles == 1:
            base += 0.10
        elif recovery_candles <= _RECOVERY_MAX_CANDLES:
            base += 0.05
        return min(base, 1.0)

    @staticmethod
    def _null_result() -> Dict[str, Any]:
        return {
            "detected":   False,
            "direction":  "NONE",
            "confidence": 0.0,
            "hunt_low":   None,
            "hunt_high":  None,
        }
