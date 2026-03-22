from __future__ import annotations

import logging
import math
from typing import Any, Dict, List

import numpy as np

logger = logging.getLogger("scanner.features")

# ── 정규화 기준값 (system_config에서 읽거나 초기값 사용) ─────────
_VOLUME_NORM_USD    = 1_000_000_000   # [초기값] 유동성 기준 $10억
_DEPTH_NORM_USD     = 500_000         # [초기값] depth 기준 $50만
_SPREAD_MAX_BPS_PCT = 0.06            # [초기값] spread 최대 허용 (%)
_ATR_MIN            = 0.5             # [초기값] ATR expansion 최솟값
_ATR_MAX            = 3.0             # [초기값] ATR expansion 최댓값
_OI_CHANGE_NORM     = 0.03            # [초기값] OI 변화율 정규화 기준
_TRADE_VEL_NORM     = 10.0            # [초기값] 체결 속도 정규화 기준
_BA_RATIO_NORM      = 0.5             # [초기값] bid/ask ratio imbalance 기준
_VWAP_DEV_NORM      = 0.5             # [초기값] VWAP 이탈 정규화 기준
_EMA_SLOPE_NORM     = 10.0            # [초기값] EMA slope 정규화 기준


def _safe_float(val: Any, default: float = 0.0) -> float:
    """None, NaN, Inf를 default로 안전하게 변환."""
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _compute_atr(klines: List[Dict[str, Any]], period: int = 14) -> List[float]:
    """
    True Range 기반 ATR 계산.
    klines: [{open, high, low, close, volume, timestamp}, ...]
    부족한 데이터 → 빈 리스트 반환.
    """
    if len(klines) < 2:
        return []
    trs: List[float] = []
    for i in range(1, len(klines)):
        h = _safe_float(klines[i].get("high"))
        l = _safe_float(klines[i].get("low"))
        pc = _safe_float(klines[i - 1].get("close"))
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    if not trs:
        return []
    # EWM 방식 ATR
    atrs: List[float] = [trs[0]]
    alpha = 1.0 / period
    for tr in trs[1:]:
        atrs.append(atrs[-1] * (1 - alpha) + tr * alpha)
    return atrs


def _compute_ema(closes: List[float], period: int) -> List[float]:
    """EWM 방식 EMA (pandas 없이 직접 구현)."""
    if not closes:
        return []
    alpha = 2.0 / (period + 1)
    emas = [closes[0]]
    for c in closes[1:]:
        emas.append(emas[-1] * (1 - alpha) + c * alpha)
    return emas


def _compute_vwap(klines: List[Dict[str, Any]]) -> List[float]:
    """일간 기준 누적 VWAP."""
    if not klines:
        return []
    pv_cum = 0.0
    v_cum = 0.0
    vwaps: List[float] = []
    for k in klines:
        c = _safe_float(k.get("close"))
        v = _safe_float(k.get("volume"))
        pv_cum += c * v
        v_cum += v
        vwaps.append(pv_cum / v_cum if v_cum > 0 else c)
    return vwaps


class ScannerFeatureCalculator:
    """
    심볼별 스캘핑 기대값 점수 계산기.
    총점 100점 = 유동성(20) + 변동성(20) + 모멘텀(20) + 참여도(15)
                + 호가창품질(10) + 펀딩편향(8) + 이벤트(7)
    """

    def compute_all_features(
        self, symbol: str, market_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        market_state: MarketDataManager.get_state(symbol) 반환 dict
        반환: 점수 딕셔너리 (총점 + 세부 점수 + raw 측정값)
        paper_mode / 데이터 부족 시 안전하게 0점 처리.
        """
        try:
            return self._compute(symbol, market_state)
        except Exception as exc:
            logger.error(
                "scanner_features compute failed symbol=%s error=%s",
                symbol, exc,
            )
            return self._zero_features(symbol)

    def _compute(
        self, symbol: str, market_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        # ── 원본 데이터 추출 ──────────────────────────────────
        volume_24h = _safe_float(market_state.get("volume_24h"))
        spread_bps = _safe_float(market_state.get("spread_bps"))
        funding_rate = _safe_float(market_state.get("funding_rate"))
        open_interest = _safe_float(market_state.get("open_interest"))
        oi_prev_5m = _safe_float(market_state.get("oi_prev_5m"), open_interest)

        # klines (paper_mode에서 빈 리스트 가능)
        klines_3m: List[Dict[str, Any]] = market_state.get("klines_3m") or []
        klines_1m: List[Dict[str, Any]] = market_state.get("klines_1m") or []

        recent_trades: List[Dict[str, Any]] = market_state.get("recent_trades") or []

        # ── 파생 지표 계산 ────────────────────────────────────
        closes_3m = [_safe_float(k.get("close")) for k in klines_3m]

        atrs = _compute_atr(klines_3m, period=14)
        current_atr = atrs[-1] if atrs else 0.0
        mean_atr_20 = float(np.mean(atrs[-20:])) if len(atrs) >= 2 else current_atr
        mean_atr_20 = mean_atr_20 if mean_atr_20 > 0 else 1e-9

        atr_expansion = current_atr / mean_atr_20

        ema20s = _compute_ema(closes_3m, 20)
        ema50s = _compute_ema(closes_3m, 50)
        ema20_slope = (ema20s[-1] - ema20s[-2]) if len(ema20s) >= 2 else 0.0
        ema50_slope = (ema50s[-1] - ema50s[-2]) if len(ema50s) >= 2 else 0.0

        vwaps = _compute_vwap(klines_3m)
        last_close = closes_3m[-1] if closes_3m else 0.0
        last_vwap = vwaps[-1] if vwaps else last_close
        vwap_deviation = (
            (last_close - last_vwap) / last_vwap
            if last_vwap > 0 else 0.0
        )

        # OI 변화율 (5분 기준)
        oi_change_5m_pct = (
            (open_interest - oi_prev_5m) / oi_prev_5m
            if oi_prev_5m > 0 else 0.0
        )

        # 최근 5분봉 고저 (klines_1m 5개)
        recent_1m = klines_1m[-5:] if klines_1m else []
        high_5m = max((_safe_float(k.get("high")) for k in recent_1m), default=last_close)
        low_5m = min((_safe_float(k.get("low")) for k in recent_1m), default=last_close)

        # 체결 속도 (최근 60초 체결 수)
        trade_velocity = float(len(recent_trades))

        # bid/ask ratio
        bid_ask_ratio = _safe_float(market_state.get("bid_ask_ratio"), 1.0)

        # depth USD
        depth_1pct_usd = _safe_float(market_state.get("orderbook_depth_usd"), 0.0)

        # 명세: paper_mode에서 kline이 비고 핵심 입력도 부족하면 0점 fallback
        if (
            not klines_3m and not klines_1m
            and volume_24h <= 0
            and depth_1pct_usd <= 0
            and open_interest <= 0
            and len(recent_trades) == 0
        ):
            return self._zero_features(symbol)

        # ── 점수 계산 ─────────────────────────────────────────

        # 1. liquidity_score (0~20점)
        volume_score = min(volume_24h / _VOLUME_NORM_USD, 1.0) * 7
        depth_score = min(depth_1pct_usd / _DEPTH_NORM_USD, 1.0) * 7
        spread_score = max(
            0.0,
            (_SPREAD_MAX_BPS_PCT - spread_bps / 100) / _SPREAD_MAX_BPS_PCT
        ) * 6
        liquidity_score = min(volume_score + depth_score + spread_score, 20.0)

        # 2. volatility_score (0~20점)
        atr_score = min(max(atr_expansion, _ATR_MIN), _ATR_MAX)
        norm_atr = (atr_score - _ATR_MIN) / (_ATR_MAX - _ATR_MIN) * 20
        range_exp = (high_5m - low_5m) / current_atr if current_atr > 0 else 0.0
        volatility_score = min(
            (norm_atr + min(range_exp, 1.0) * 5) / 2, 20.0
        )

        # 3. momentum_score (0~20점)
        atr_ref = current_atr if current_atr > 0 else 1e-9
        ema20_slope_norm = ema20_slope / atr_ref
        slope_score = min(abs(ema20_slope_norm) * _EMA_SLOPE_NORM, 10.0)
        vwap_score = min(abs(vwap_deviation) / (_VWAP_DEV_NORM / 100), 1.0) * 10
        momentum_score = min(slope_score + vwap_score, 20.0)

        # 4. participation_score (0~15점)
        oi_score = min(abs(oi_change_5m_pct) / _OI_CHANGE_NORM, 1.0) * 8
        velocity_score = min(trade_velocity / _TRADE_VEL_NORM, 1.0) * 7
        participation_score = min(oi_score + velocity_score, 15.0)

        # 5. orderbook_quality (0~10점)
        orderbook_quality = min(
            abs(bid_ask_ratio - 1.0) / _BA_RATIO_NORM, 1.0
        ) * 10

        # 6. funding_imbalance_score (0~8점)
        rate = abs(funding_rate)
        if rate >= 0.001:
            funding_imbalance_score = 8.0
        elif rate >= 0.0005:
            funding_imbalance_score = 5.0
        elif rate >= 0.0002:
            funding_imbalance_score = 3.0
        else:
            funding_imbalance_score = 0.0

        # 7. event_score (0~7점)
        liquidation_nearby = (
            1 if (
                oi_change_5m_pct < -0.02
                and (high_5m - low_5m) >= current_atr * 1.5
            ) else 0
        )
        breakout_trace = 0
        if len(klines_3m) >= 10:
            recent_10 = klines_3m[-10:]
            for k in recent_10:
                h = _safe_float(k.get("high"))
                l = _safe_float(k.get("low"))
                if (h - l) >= current_atr * 2.0:
                    breakout_trace = 1
                    break
        event_score = float(liquidation_nearby * 4 + breakout_trace * 3)

        # ── 총점 ──────────────────────────────────────────────
        total_score = min(
            liquidity_score + volatility_score + momentum_score
            + participation_score + orderbook_quality
            + funding_imbalance_score + event_score,
            100.0,
        )

        return {
            "symbol":                  symbol,
            "liquidity_score":         round(liquidity_score, 4),
            "volatility_score":        round(volatility_score, 4),
            "momentum_score":          round(momentum_score, 4),
            "participation_score":     round(participation_score, 4),
            "orderbook_quality":       round(orderbook_quality, 4),
            "funding_imbalance_score": round(funding_imbalance_score, 4),
            "event_score":             round(event_score, 4),
            "total_score":             round(total_score, 4),
            "raw": {
                "volume_24h":        volume_24h,
                "spread_bps":        spread_bps,
                "atr_expansion":     round(atr_expansion, 6),
                "ema20_slope":       round(ema20_slope, 6),
                "ema50_slope":       round(ema50_slope, 6),
                "vwap_deviation":    round(vwap_deviation, 6),
                "oi_change_5m_pct":  round(oi_change_5m_pct, 6),
                "oi_change_15m_pct": 0.0,
                "bid_ask_ratio":     round(bid_ask_ratio, 6),
                "funding_rate":      funding_rate,
                "trade_velocity":    trade_velocity,
            },
        }

    @staticmethod
    def _zero_features(symbol: str) -> Dict[str, Any]:
        """데이터 부족 / 예외 발생 시 반환하는 0점 구조."""
        return {
            "symbol":                  symbol,
            "liquidity_score":         0.0,
            "volatility_score":        0.0,
            "momentum_score":          0.0,
            "participation_score":     0.0,
            "orderbook_quality":       0.0,
            "funding_imbalance_score": 0.0,
            "event_score":             0.0,
            "total_score":             0.0,
            "raw": {
                "volume_24h":        0.0,
                "spread_bps":        0.0,
                "atr_expansion":     0.0,
                "ema20_slope":       0.0,
                "ema50_slope":       0.0,
                "vwap_deviation":    0.0,
                "oi_change_5m_pct":  0.0,
                "oi_change_15m_pct": 0.0,
                "bid_ask_ratio":     1.0,
                "funding_rate":      0.0,
                "trade_velocity":    0.0,
            },
        }
