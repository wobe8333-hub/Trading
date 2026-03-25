from __future__ import annotations

import logging
import math
from typing import Any, Dict, List

logger = logging.getLogger("macro_filter.features")

# ── 임계값 ───────────────────────────────────────────────────
_VWAP_NEAR_BAND_PCT = 0.001   # [초기값] VWAP ±0.1% 이내 → "NEAR"
_VOLUME_SPIKE_RATIO = 3.0     # [검증값] 20봉 평균 대비 3배 이상 → spike


def _safe(val: Any, default: float = 0.0) -> float:
    """None / NaN / Inf 를 default로 안전 변환."""
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _compute_ema(closes: List[float], period: int) -> List[float]:
    """EWM 방식 EMA. 데이터 부족 시 빈 리스트 반환."""
    if not closes:
        return []
    alpha = 2.0 / (period + 1)
    emas = [closes[0]]
    for c in closes[1:]:
        emas.append(emas[-1] * (1 - alpha) + c * alpha)
    return emas


def _compute_atr(klines: List[Dict[str, Any]], period: int = 14) -> List[float]:
    """True Range 기반 ATR. 데이터 부족 시 빈 리스트 반환."""
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
    """일간 기준 누적 VWAP 최종값 반환. 데이터 없으면 0.0."""
    pv_cum = v_cum = 0.0
    for k in klines:
        c = _safe(k.get("close"))
        v = _safe(k.get("volume"))
        pv_cum += c * v
        v_cum += v
    return pv_cum / v_cum if v_cum > 0 else 0.0


class MacroFeatureCalculator:
    """
    BTC market_state → Macro 판정에 필요한 파생 지표 계산.
    """

    def compute(self, btc_state: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self._compute(btc_state)
        except Exception as exc:
            logger.error("macro_features compute failed error=%s", exc)
            return self._default_features()

    def _compute(self, btc_state: Dict[str, Any]) -> Dict[str, Any]:
        klines: List[Dict[str, Any]] = btc_state.get("klines_3m") or []
        closes = [_safe(k.get("close")) for k in klines]
        volumes = [_safe(k.get("volume")) for k in klines]

        # ── EMA 계산 ──────────────────────────────────────────
        ema20s = _compute_ema(closes, 20)
        ema50s = _compute_ema(closes, 50)
        ema200s = _compute_ema(closes, 200)

        ema20 = ema20s[-1] if ema20s else 0.0
        ema50 = ema50s[-1] if ema50s else 0.0
        ema200 = ema200s[-1] if ema200s else 0.0

        # ── VWAP ──────────────────────────────────────────────
        vwap = _compute_vwap(klines)

        # ── ATR + ATR Expansion ────────────────────────────────
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

        # ── OI 변화율 ─────────────────────────────────────────
        oi_now = _safe(btc_state.get("open_interest"), 1.0)
        oi_prev = _safe(btc_state.get("oi_prev_5m"), oi_now)
        oi_change_pct = (
            (oi_now - oi_prev) / oi_prev
            if oi_prev > 1e-9 else 0.0
        )

        # ── Funding Bias ───────────────────────────────────────
        funding_bias = _safe(btc_state.get("funding_rate"))

        # ── Volume Spike ───────────────────────────────────────
        volume_spike = False
        if len(volumes) >= 21:
            avg_vol = sum(volumes[-21:-1]) / 20
            if avg_vol > 0 and volumes[-1] >= avg_vol * _VOLUME_SPIKE_RATIO:
                volume_spike = True

        # ── Price vs VWAP ──────────────────────────────────────
        last_price = _safe(btc_state.get("last_price"))
        if vwap > 0 and last_price > 0:
            deviation = (last_price - vwap) / vwap
            if abs(deviation) <= _VWAP_NEAR_BAND_PCT:
                price_vs_vwap = "NEAR"
            elif deviation > 0:
                price_vs_vwap = "ABOVE"
            else:
                price_vs_vwap = "BELOW"
        else:
            price_vs_vwap = "NEAR"

        # ── EMA Alignment ──────────────────────────────────────
        if ema20 > 0 and ema50 > 0:
            if ema20 > ema50:
                ema_alignment = "BULL"
            elif ema20 < ema50:
                ema_alignment = "BEAR"
            else:
                ema_alignment = "NEUTRAL"
        else:
            ema_alignment = "NEUTRAL"

        logger.info(
            "macro_features ema20=%.2f ema50=%.2f ema200=%.2f "
            "vwap=%.2f atr=%.5f atr_exp=%.4f "
            "oi_chg=%.6f funding=%.6f vol_spike=%s "
            "price_vs_vwap=%s ema_align=%s",
            ema20, ema50, ema200,
            vwap, atr_14, atr_expansion,
            oi_change_pct, funding_bias, volume_spike,
            price_vs_vwap, ema_alignment,
        )
        return {
            "ema20":         round(ema20, 6),
            "ema50":         round(ema50, 6),
            "ema200":        round(ema200, 6),
            "vwap":          round(vwap, 6),
            "atr_14":        round(atr_14, 6),
            "atr_expansion": round(atr_expansion, 6),
            "oi_change_pct": round(oi_change_pct, 6),
            "funding_bias":  funding_bias,
            "volume_spike":  volume_spike,
            "price_vs_vwap": price_vs_vwap,
            "ema_alignment": ema_alignment,
        }

    @staticmethod
    def _default_features() -> Dict[str, Any]:
        """예외 / 데이터 없을 때 반환하는 기본값."""
        return {
            "ema20":         0.0,
            "ema50":         0.0,
            "ema200":        0.0,
            "vwap":          0.0,
            "atr_14":        0.0,
            "atr_expansion": 1.0,
            "oi_change_pct": 0.0,
            "funding_bias":  0.0,
            "volume_spike":  False,
            "price_vs_vwap": "NEAR",
            "ema_alignment": "NEUTRAL",
        }
