from __future__ import annotations

import logging
import math
from typing import Any, Dict

logger = logging.getLogger("orderflow.imbalance")

# ── 감지 임계값 ───────────────────────────────────────────────
_BID_ASK_RATIO_HIGH      = 2.0    # [초기값] bid/ask > 2.0 → 매수 우세
_BID_ASK_RATIO_LOW       = 0.5    # [초기값] bid/ask < 0.5 → 매도 우세
_ASK_DEPTH_SPIKE_RATIO   = 0.5    # [초기값] ask_depth 50% 증가
_PRICE_STABLE_THRESHOLD  = 0.3    # [초기값] 가격 변화 |impulse| <= 0.3 ATR


def _safe(val: Any, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


class ImbalanceDetector:
    """
    호가창 불균형 이벤트 감지기.
    """

    def detect(
        self, symbol: str, market_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            return self._detect(symbol, market_state)
        except Exception as exc:
            logger.error(
                "imbalance_detector detect failed symbol=%s error=%s",
                symbol, exc,
            )
            return self._null_result()

    def _detect(
        self, symbol: str, market_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        bid_ask_ratio    = _safe(market_state.get("bid_ask_ratio"), 1.0)
        ask_depth_chg    = _safe(market_state.get("ask_depth_change_pct"), 0.0)
        price_impulse    = _safe(market_state.get("price_impulse_atr"), 0.0)
        _ = _safe(market_state.get("orderbook_bid_depth"))
        _ = _safe(market_state.get("orderbook_ask_depth"))

        # ── IMBALANCE_BREAK ───────────────────────────────────
        # bid/ask 비율이 극단적이고 해당 방향으로 가격 돌파
        if bid_ask_ratio > _BID_ASK_RATIO_HIGH and price_impulse > 0:  # [초기값]
            confidence = min(
                0.5 + (bid_ask_ratio - _BID_ASK_RATIO_HIGH) * 0.1,
                1.0,
            )
            logger.info(
                "imbalance_detector IMBALANCE_BREAK BUY symbol=%s conf=%.2f",
                symbol, confidence,
            )
            return {
                "event_type": "IMBALANCE_BREAK",
                "confidence": round(confidence, 4),
                "direction":  "BUY",
            }

        if bid_ask_ratio < _BID_ASK_RATIO_LOW and price_impulse < 0:  # [초기값]
            confidence = min(
                0.5 + (_BID_ASK_RATIO_LOW - bid_ask_ratio) * 0.5,
                1.0,
            )
            logger.info(
                "imbalance_detector IMBALANCE_BREAK SELL symbol=%s conf=%.2f",
                symbol, confidence,
            )
            return {
                "event_type": "IMBALANCE_BREAK",
                "confidence": round(confidence, 4),
                "direction":  "SELL",
            }

        # ── ABSORPTION_EVENT ──────────────────────────────────
        # 대량 매도 물량 출현(ask_depth 50% 이상 증가) + 가격 유지
        if (
            ask_depth_chg  > _ASK_DEPTH_SPIKE_RATIO            # [초기값]
            and abs(price_impulse) <= _PRICE_STABLE_THRESHOLD   # [초기값]
        ):
            confidence = min(0.5 + ask_depth_chg * 0.2, 1.0)
            logger.info(
                "imbalance_detector ABSORPTION_EVENT symbol=%s conf=%.2f",
                symbol, confidence,
            )
            return {
                "event_type": "ABSORPTION_EVENT",
                "confidence": round(confidence, 4),
                "direction":  "BUY",
            }

        return self._null_result()

    @staticmethod
    def _null_result() -> Dict[str, Any]:
        return {
            "event_type": None,
            "confidence": 0.0,
            "direction":  "NONE",
        }
