from __future__ import annotations

from typing import Dict, Tuple

# ── 점수 → 포지션 비율 매핑 ───────────────────────────────────
# 구현지침서 명세 그대로
SCORE_TO_SCALE: Dict[Tuple[int, int], float] = {
    (90, 100): 1.0,   # [검증값]
    (80,  89): 0.7,   # [검증값]
    (70,  79): 0.4,   # [검증값]
    (0,   69): 0.0,   # [검증값] 진입 금지
}

# ── 점수 → 진입 품질 등급 매핑 ────────────────────────────────
SCORE_TO_QUALITY: Dict[Tuple[int, int], str] = {
    (90, 100): "A+",      # [검증값]
    (80,  89): "A",       # [검증값]
    (70,  79): "B",       # [검증값]
    (0,   69): "REJECT",  # [검증값]
}


def score_to_scale(total_score: float) -> float:
    """total_score → position_scale 변환."""
    s = int(total_score)
    if s >= 90:
        return 1.0
    elif s >= 80:
        return 0.7
    elif s >= 70:
        return 0.4
    return 0.0


def score_to_quality(total_score: float) -> str:
    """total_score → entry_quality 등급 변환."""
    s = int(total_score)
    if s >= 90:
        return "A+"
    elif s >= 80:
        return "A"
    elif s >= 70:
        return "B"
    return "REJECT"

