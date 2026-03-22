from __future__ import annotations

import logging
import math
from typing import Any, Dict, List

from src.core.regime_engine.regime_rules import REGIME_RULES

logger = logging.getLogger("regime_engine")


def _safe(val: Any, default: float = 0.0) -> float:
    """None / NaN / Inf → default 안전 변환."""
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _compute_ema(closes: List[float], period: int) -> List[float]:
    """EWM 방식 EMA. 데이터 없으면 빈 리스트."""
    if not closes:
        return []
    alpha = 2.0 / (period + 1)
    emas = [closes[0]]
    for c in closes[1:]:
        emas.append(emas[-1] * (1 - alpha) + c * alpha)
    return emas


def _compute_atr(klines: List[Dict[str, Any]], period: int = 14) -> List[float]:
    """True Range 기반 ATR. 데이터 부족 시 빈 리스트."""
    if len(klines) < 2:
        return []
    trs: List[float] = []
    for i in range(1, len(klines)):
        h = _safe(klines[i].get("high"))
        l = _safe(klines[i].get("low"))
        pc = _safe(klines[i - 1].get("close"))
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if not trs:
        return []
    alpha = 1.0 / period
    atrs = [trs[0]]
    for tr in trs[1:]:
        atrs.append(atrs[-1] * (1 - alpha) + tr * alpha)
    return atrs


def _compute_vwap(klines: List[Dict[str, Any]]) -> float:
    """일간 기준 누적 VWAP 최종값. 데이터 없으면 0.0."""
    pv = v = 0.0
    for k in klines:
        c = _safe(k.get("close"))
        vol = _safe(k.get("volume"))
        pv += c * vol
        v += vol
    return pv / v if v > 0 else 0.0


def _detect_hh_hl(
    highs: List[float], lows: List[float], lookback: int = 10
) -> bool:
    """
    최근 lookback봉 내 HH(Higher High) + HL(Higher Low) 각 2회 이상.
    """
    n = min(len(highs), len(lows), lookback)
    if n < 2:
        return False
    hh_count = sum(
        highs[i] > highs[i - 1]
        for i in range(1, n)
    )
    hl_count = sum(
        lows[i] > lows[i - 1]
        for i in range(1, n)
    )
    min_count = REGIME_RULES["TREND_UP"]["hh_hl_min_count"]   # [초기값] 2
    return hh_count >= min_count and hl_count >= min_count


def _detect_ll_lh(
    highs: List[float], lows: List[float], lookback: int = 10
) -> bool:
    """
    최근 lookback봉 내 LL(Lower Low) + LH(Lower High) 각 2회 이상.
    """
    n = min(len(highs), len(lows), lookback)
    if n < 2:
        return False
    ll_count = sum(
        lows[i] < lows[i - 1]
        for i in range(1, n)
    )
    lh_count = sum(
        highs[i] < highs[i - 1]
        for i in range(1, n)
    )
    min_count = REGIME_RULES["TREND_DOWN"]["ll_lh_min_count"]  # [초기값] 2
    return ll_count >= min_count and lh_count >= min_count


class MarketRegimeEngine:
    """
    심볼별 시장 구조(Regime) 판정 엔진.
    """

    def __init__(self) -> None:
        self.regimes: Dict[str, str] = {}

    def get_regime(
        self, symbol: str, market_state: Dict[str, Any]
    ) -> str:
        """
        market_state를 받아 Regime 문자열 반환.
        반환값: "TREND_UP" / "TREND_DOWN" / "RANGE" / "EXPANSION"
        예외 발생 시 "RANGE" 반환 — 시스템 중단 없음.
        """
        try:
            regime = self._evaluate(symbol, market_state)
        except Exception as exc:
            logger.error(
                "regime_engine get_regime failed symbol=%s error=%s",
                symbol, exc,
            )
            regime = "RANGE"

        self.regimes[symbol] = regime
        logger.info("regime_engine symbol=%s regime=%s", symbol, regime)
        return regime

    def get_all_regimes(self) -> Dict[str, str]:
        """전체 심볼의 최신 Regime 딕셔너리 반환."""
        return dict(self.regimes)

    def _evaluate(
        self, symbol: str, market_state: Dict[str, Any]
    ) -> str:
        klines: List[Dict[str, Any]] = market_state.get("klines_3m") or []
        if not klines:
            return "RANGE"

        closes = [_safe(k.get("close")) for k in klines]
        highs = [_safe(k.get("high")) for k in klines]
        lows = [_safe(k.get("low")) for k in klines]
        volumes = [_safe(k.get("volume")) for k in klines]

        ema20s = _compute_ema(closes, 20)
        ema50s = _compute_ema(closes, 50)
        ema20 = ema20s[-1] if ema20s else 0.0
        ema50 = ema50s[-1] if ema50s else 0.0

        atrs = _compute_atr(klines, period=14)
        atr_14 = atrs[-1] if atrs else 0.0
        mean_atr20 = (
            sum(atrs[-20:]) / len(atrs[-20:])
            if len(atrs) >= 2 else atr_14
        )
        atr_expansion = (
            atr_14 / mean_atr20
            if mean_atr20 > 1e-9 else 1.0
        )

        volume_ratio = 1.0
        if len(volumes) >= 21:
            avg_vol = sum(volumes[-21:-1]) / 20
            if avg_vol > 0:
                volume_ratio = volumes[-1] / avg_vol

        vwap = _compute_vwap(klines)
        last_price = _safe(market_state.get("last_price"))

        exp_rules = REGIME_RULES["EXPANSION"]
        if (
            atr_expansion >= exp_rules["atr_expansion_min"]
            and volume_ratio >= exp_rules["volume_spike_ratio"]
        ):
            return "EXPANSION"

        # RANGE 조건 우선 체크 (EXPANSION 제외 후 횡보 판정)
        range_rules = REGIME_RULES["RANGE"]
        ema_diff_pct = (
            abs(ema20 - ema50) / ema50
            if ema50 > 1e-9 else float("inf")
        )
        if (
            ema_diff_pct <= range_rules["ema_diff_max_pct"]   # [초기값] 0.3%
            and atr_expansion <= range_rules["atr_expansion_max"]  # [초기값] 1.0
        ):
            return "RANGE"

        price_above_vwap = (
            last_price > vwap
            if (vwap > 0 and last_price > 0) else False
        )
        if (
            ema20 > ema50
            and price_above_vwap
            and _detect_hh_hl(highs[-10:], lows[-10:], lookback=10)
        ):
            return "TREND_UP"

        price_below_vwap = (
            last_price < vwap
            if (vwap > 0 and last_price > 0) else False
        )
        if (
            ema20 < ema50
            and price_below_vwap
            and _detect_ll_lh(highs[-10:], lows[-10:], lookback=10)
        ):
            return "TREND_DOWN"

        return "RANGE"
