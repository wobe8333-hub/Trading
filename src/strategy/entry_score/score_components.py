from __future__ import annotations

import logging
import math
from typing import Any, Dict, List

from src.utils.math_utils import compute_ema, compute_atr, compute_vwap

logger = logging.getLogger("entry_score.components")

# ── 각 컴포넌트 최대 점수 ──────────────────────────────────────
_MAX_TREND = 15  # [검증값]
_MAX_VWAP = 15  # [검증값]
_MAX_REGIME = 15  # [검증값]
_MAX_SCANNER = 15  # [검증값]
_MAX_VOLUME = 10  # [검증값]
_MAX_VOLATILITY = 10  # [검증값]
_MAX_ORDERFLOW = 10  # [검증값]
_MAX_PATTERN = 10  # [검증값]
_MAX_FUNDING = 8  # [검증값]

# ── 기타 임계값 ───────────────────────────────────────────────
_VWAP_ABOVE_BONUS = 3.0  # [초기값] VWAP 위/아래 보너스
_ATR_VWAP_NORM = 2.0  # [초기값] VWAP 이탈 정규화 기준 (ATR 배수)
_VOL_SPIKE_HIGH = 1.5  # [초기값]
_VOL_SPIKE_MED = 1.2  # [초기값]
_VOL_SPIKE_LOW = 1.0  # [초기값]
_ATR_EXP_OK_MIN = 0.8  # [초기값]
_ATR_EXP_OK_MAX = 1.5  # [초기값]
_ATR_EXP_WARN_MIN = 0.5  # [초기값]
_ATR_EXP_WARN_MAX = 2.0  # [초기값]
_FUNDING_EXTREME = 0.001  # [검증값]
_FUNDING_MED = 0.0005  # [초기값]
_FUNDING_MILD = 0.0002  # [초기값] (LONG 방향 사용)


def _safe(val: Any, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _clip(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


class ScoreComponents:
    """
    진입 점수 8개 컴포넌트 + Funding Bonus 계산기.

    각 컴포넌트 최대 점수 합산:
    trend(15) + vwap(15) + regime(15) + scanner(15)
    + volume(10) + volatility(10) + orderflow(10) + pattern(10) = 100
    + funding_bonus(0~8) → min(total + bonus, 100)
    """

    # ── 1. Trend Score (0~15) ─────────────────────────────────

    def compute_trend_score(
        self,
        market_state: Dict[str, Any],
        direction: str = "LONG",
    ) -> float:
        """
        스캘핑 최적화: EMA5/EMA20/EMA50 기반
        LONG:  EMA5>EMA20>EMA50=15 / EMA5>EMA20=10 / EMA5<EMA20=5 / 역정렬=0
        SHORT: EMA5<EMA20<EMA50=15 / EMA5<EMA20=10 / EMA5>EMA20=5 / 역정렬=0
        가격 VWAP 위치 보정: 방향 일치 +3 / 불일치 -3  clip 0~15
        """
        try:
            klines: List[Dict] = market_state.get("klines_3m") or []
            closes = [_safe(k.get("close")) for k in klines]
            volumes = [_safe(k.get("volume")) for k in klines]

            ema5s = compute_ema(closes, 5)  # [초기값] 3분봉×5  = 15분
            ema20s = compute_ema(closes, 20)  # [초기값] 3분봉×20 = 60분
            ema50s = compute_ema(closes, 50)  # [초기값] 3분봉×50 = 150분
            _lookback = 20
            vwaps = []
            for _i in range(len(closes)):
                _s = max(0, _i - _lookback + 1)
                _rc = closes[_s:_i+1]; _rv = volumes[_s:_i+1]
                _pv = sum(c*v for c,v in zip(_rc,_rv)); _cv = sum(_rv)
                vwaps.append(_pv/_cv if _cv > 0 else closes[_i])

            if not (ema5s and ema20s and ema50s):
                return 0.0

            ema5 = ema5s[-1]
            ema20 = ema20s[-1]
            ema50 = ema50s[-1]
            vwap = vwaps[-1] if vwaps else 0.0
            price = closes[-1] if closes else 0.0

            # 방향별 EMA 정렬 점수
            if direction == "LONG":
                if ema5 > ema20 > ema50:
                    base = 15.0  # [초기값] 완전 정배열
                elif ema5 > ema20:
                    base = 10.0  # [초기값] 단기 상승
                elif ema5 < ema20:
                    base = 5.0  # [초기값] 단기 하락 (추세 없음)
                else:
                    base = 0.0
            else:  # SHORT
                if ema5 < ema20 < ema50:
                    base = 15.0  # [초기값] 완전 역배열 = SHORT 최적
                elif ema5 < ema20:
                    base = 10.0  # [초기값] 단기 하락
                elif ema5 > ema20:
                    base = 5.0  # [초기값] 단기 상승 (추세 없음)
                else:
                    base = 0.0

            # VWAP 위치 보정
            if vwap > 0 and price > 0:
                if price > vwap:
                    base += (
                        _VWAP_ABOVE_BONUS
                        if direction == "LONG"
                        else -_VWAP_ABOVE_BONUS
                    )
                else:
                    base += (
                        -_VWAP_ABOVE_BONUS
                        if direction == "LONG"
                        else _VWAP_ABOVE_BONUS
                    )

            result_trend = _clip(base, 0.0, float(_MAX_TREND))
            logger.debug(
                "score_trend dir=%s ema5=%.5f ema20=%.5f ema50=%.5f "
                "vwap=%.5f price=%.5f base_before_clip=%.2f result=%.4f",
                direction,
                ema5s[-1] if ema5s else 0.0,
                ema20s[-1] if ema20s else 0.0,
                ema50s[-1] if ema50s else 0.0,
                vwaps[-1] if vwaps else 0.0,
                closes[-1] if closes else 0.0,
                base,
                result_trend,
            )
            return result_trend
        except Exception as exc:
            logger.error("compute_trend_score failed error=%s", exc)
            return 0.0

    # ── 2. VWAP Score (0~15) ──────────────────────────────────

    def compute_vwap_score(
        self,
        market_state: Dict[str, Any],
        direction: str,
    ) -> float:
        """
        구현지침서 명세:
        - VWAP 이탈 방향 일치: +8
        - VWAP 이탈 거리 비례: +0~7 (ATR 기준 정규화)
        """
        try:
            klines: List[Dict] = market_state.get("klines_3m") or []
            closes = [_safe(k.get("close")) for k in klines]
            highs = [_safe(k.get("high")) for k in klines]
            lows = [_safe(k.get("low")) for k in klines]
            volumes = [_safe(k.get("volume")) for k in klines]

            if not closes:
                return 0.0

            _lookback = 20
            vwaps = []
            for _i in range(len(closes)):
                _s = max(0, _i - _lookback + 1)
                _rc = closes[_s:_i+1]; _rv = volumes[_s:_i+1]
                _pv = sum(c*v for c,v in zip(_rc,_rv)); _cv = sum(_rv)
                vwaps.append(_pv/_cv if _cv > 0 else closes[_i])
            atrs = compute_atr(highs, lows, closes, 14)

            vwap = vwaps[-1] if vwaps else 0.0
            atr = atrs[-1] if atrs else 0.0
            price = closes[-1] if closes else 0.0

            if vwap <= 0 or atr <= 1e-9:
                return 0.0

            deviation = price - vwap

            # 방향 일치 여부
            if direction == "LONG" and deviation > 0:
                direction_score = 8.0  # [검증값]
            elif direction == "SHORT" and deviation < 0:
                direction_score = 8.0
            else:
                direction_score = 0.0

            # 이탈 거리 비례 (0~7)
            distance_ratio = abs(deviation) / (atr * _ATR_VWAP_NORM)  # [초기값]
            distance_score = _clip(distance_ratio * 7.0, 0.0, 7.0)  # [검증값]

            result_vwap = _clip(direction_score + distance_score, 0.0, float(_MAX_VWAP))
            logger.debug(
                "score_vwap dir=%s deviation=%.6f atr=%.5f "
                "dir_score=%.1f dist_score=%.4f result=%.4f",
                direction, deviation, atr,
                direction_score, distance_score, result_vwap,
            )
            return result_vwap
        except Exception as exc:
            logger.error("compute_vwap_score failed error=%s", exc)
            return 0.0

    # ── 3. Regime Alignment Score (0 or 15) ──────────────────

    def compute_regime_alignment_score(
        self,
        strategy_name: str,
        regime: str,
    ) -> float:
        """
        전략 허용 Regime → 15
        금지 Regime → 0
        """
        try:
            from src.utils.config_loader import load_strategy_config

            cfg = load_strategy_config()
            strat_cfg = cfg.get(strategy_name, {})

            if regime in strat_cfg.get("forbidden_regimes", []):
                _score_r = 0.0
            elif regime in strat_cfg.get("allowed_regimes", []):
                _score_r = float(_MAX_REGIME)
            else:
                _score_r = 0.0
            logger.debug(
                "score_regime strat=%s regime=%s allowed=%s forbidden=%s result=%.1f",
                strategy_name, regime,
                strat_cfg.get("allowed_regimes", []),
                strat_cfg.get("forbidden_regimes", []),
                _score_r,
            )
            return _score_r
        except Exception as exc:
            logger.error("compute_regime_alignment_score failed error=%s", exc)
            return 0.0

    # ── 4. Scanner Bonus (5, 10, or 15) ──────────────────────

    @staticmethod
    def compute_scanner_bonus(grade: str) -> float:
        """
        구현지침서 명세:
        S: 15 / A: 10 / B: 5 / 기타: 0
        """
        mapping = {"S": 15.0, "A": 10.0, "B": 5.0}  # [검증값]
        _bonus = mapping.get(grade, 0.0)
        logger.debug("score_scanner grade=%s bonus=%.1f", grade, _bonus)
        return _bonus

    # ── 5. Volume Score (0~10) ───────────────────────────────

    def compute_volume_score(
        self,
        market_state: Dict[str, Any],
    ) -> float:
        """
        구현지침서 명세:
        1.5배 이상: 10 / 1.2~1.5배: 7 / 1.0~1.2배: 5 / 미만: 2
        """
        try:
            klines: List[Dict] = market_state.get("klines_3m") or []
            volumes = [_safe(k.get("volume")) for k in klines]

            if len(volumes) < 21:
                return 2.0

            avg20 = sum(volumes[-21:-1]) / 20
            if avg20 <= 0:
                return 2.0

            ratio = volumes[-1] / avg20

            if ratio >= _VOL_SPIKE_HIGH:
                _score_v = 10.0
            elif ratio >= _VOL_SPIKE_MED:
                _score_v = 7.0
            elif ratio >= _VOL_SPIKE_LOW:
                _score_v = 5.0
            else:
                _score_v = 2.0
            logger.debug(
                "score_volume vol_last=%.2f avg20=%.2f ratio=%.3f result=%.1f",
                volumes[-1] if volumes else 0.0, avg20, ratio, _score_v,
            )
            return _score_v
        except Exception as exc:
            logger.error("compute_volume_score failed error=%s", exc)
            return 0.0

    # ── 6. Volatility Score (0~10) ────────────────────────────

    def compute_volatility_score(
        self,
        market_state: Dict[str, Any],
    ) -> float:
        """
        구현지침서 명세:
        ATR expansion 0.8~1.5배: 10
        0.5~0.8 또는 1.5~2.0: 6
        범위 외: 2
        """
        try:
            klines: List[Dict] = market_state.get("klines_3m") or []
            closes = [_safe(k.get("close")) for k in klines]
            highs = [_safe(k.get("high")) for k in klines]
            lows = [_safe(k.get("low")) for k in klines]

            atrs = compute_atr(highs, lows, closes, 14)
            if not atrs:
                return 2.0

            atr_last = atrs[-1]
            mean_atr20 = (
                sum(atrs[-20:]) / len(atrs[-20:]) if len(atrs) >= 20 else atr_last
            )
            if mean_atr20 <= 1e-9:
                return 2.0

            expansion = atr_last / mean_atr20

            if _ATR_EXP_OK_MIN <= expansion <= _ATR_EXP_OK_MAX:
                _score_vola = 10.0
            elif (
                (_ATR_EXP_WARN_MIN <= expansion < _ATR_EXP_OK_MIN)
                or (_ATR_EXP_OK_MAX < expansion <= _ATR_EXP_WARN_MAX)
            ):
                _score_vola = 6.0
            else:
                _score_vola = 2.0
            logger.debug(
                "score_volatility atr=%.5f mean_atr20=%.5f expansion=%.4f result=%.1f",
                atr_last, mean_atr20, expansion, _score_vola,
            )
            return _score_vola
        except Exception as exc:
            logger.error("compute_volatility_score failed error=%s", exc)
            return 0.0

    # ── 7. Orderflow Score (0~10) ─────────────────────────────

    @staticmethod
    def compute_orderflow_score(orderflow_state: Dict[str, Any]) -> float:
        """
        구현지침서 명세:
        max_confidence * 10
        """
        try:
            max_conf = _safe(orderflow_state.get("max_confidence"), 0.0)
            _score_of = _clip(max_conf * 10.0, 0.0, float(_MAX_ORDERFLOW))
            logger.debug(
                "score_orderflow max_conf=%.4f result=%.4f",
                max_conf, _score_of,
            )
            return _score_of
        except Exception as exc:
            logger.error("compute_orderflow_score failed error=%s", exc)
            return 0.0

    # ── 8. Pattern Quality Score (0~10) ──────────────────────

    @staticmethod
    def compute_pattern_quality_score(layer_hit: Dict[str, Any]) -> float:
        """
        구현지침서 명세:
        layer1: +3.3 / layer2: +3.3 / layer3: +3.4
        """
        score = 0.0
        if layer_hit.get("layer1"):
            score = round(score + 3.3, 10)
        if layer_hit.get("layer2"):
            score = round(score + 3.3, 10)
        if layer_hit.get("layer3"):
            score = round(score + 3.4, 10)
        _score_pat = round(_clip(score, 0.0, float(_MAX_PATTERN)), 4)
        logger.debug(
            "score_pattern l1=%s l2=%s l3=%s result=%.4f",
            layer_hit.get("layer1"), layer_hit.get("layer2"),
            layer_hit.get("layer3"), _score_pat,
        )
        return _score_pat

    # ── 9. Funding Bonus (0~8) ────────────────────────────────

    @staticmethod
    def compute_funding_bonus(funding_rate: float, direction: str) -> float:
        """
        구현지침서 명세:
        SHORT: rate >= 0.001 → 8 / rate >= 0.0005 → 4
        LONG:  rate <= -0.0005 → 8 / rate <= -0.0002 → 4
        그 외: 0
        """
        rate = _safe(funding_rate)
        if direction == "SHORT":
            if rate >= _FUNDING_EXTREME:
                _bonus_f = 8.0
            elif rate >= _FUNDING_MED:
                _bonus_f = 4.0
            else:
                _bonus_f = 0.0
        elif direction == "LONG":
            if rate <= -_FUNDING_MED:
                _bonus_f = 8.0
            elif rate <= -_FUNDING_MILD:
                _bonus_f = 4.0
            else:
                _bonus_f = 0.0
        else:
            _bonus_f = 0.0
        logger.debug(
            "score_funding dir=%s rate=%.6f bonus=%.1f",
            direction, rate, _bonus_f,
        )
        return _bonus_f

