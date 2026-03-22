from __future__ import annotations

from typing import Any, Dict

# ── Regime 판정 규칙 상수 ─────────────────────────────────────
# 모든 값은 [초기값] 또는 [검증값] 태그로 구분한다.
# 변경 시 parameter_validator가 50거래 후 자동 검증한다.

REGIME_RULES: Dict[str, Dict[str, Any]] = {
    "EXPANSION": {
        "atr_expansion_min":  1.8,   # [초기값] 현재 ATR / 20봉 평균 ATR > 1.8
        "volume_spike_ratio": 2.0,   # [초기값] 최근 봉 거래량 / 20봉 평균 >= 2.0
    },
    "TREND_UP": {
        "ema20_above_ema50": True,   # EMA20 > EMA50
        "price_above_vwap":  True,   # 현재가 > VWAP
        "hh_hl_min_count":   2,      # [초기값] 최근 10봉 내 HH+HL 각 2회 이상
    },
    "TREND_DOWN": {
        "ema20_below_ema50": True,   # EMA20 < EMA50
        "price_below_vwap":  True,   # 현재가 < VWAP
        "ll_lh_min_count":   2,      # [초기값] 최근 10봉 내 LL+LH 각 2회 이상
    },
    "RANGE": {
        "ema_diff_max_pct":   0.003, # [초기값] |EMA20 - EMA50| / EMA50 <= 0.3%
        "atr_expansion_max":  1.0,   # [초기값] ATR expansion <= 1.0 (감소/유지)
    },
}

# 판정 우선순위 (인덱스 낮을수록 우선)
REGIME_PRIORITY = ["EXPANSION", "TREND_UP", "TREND_DOWN", "RANGE"]

# 유효한 Regime 집합 (반환값 검증용)
VALID_REGIMES = frozenset(REGIME_PRIORITY)
