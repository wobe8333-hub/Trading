from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

import yaml

logger = logging.getLogger("scanner.ranker")

_BLACKLIST_PATH = Path("config/symbol_blacklist.yaml")
_MIN_SCORE = 25.0    # [초기값] 실제 API 데이터 기준 점수 분포 반영


def _load_blacklist() -> List[str]:
    try:
        if _BLACKLIST_PATH.is_file():
            data = yaml.safe_load(_BLACKLIST_PATH.read_text(encoding="utf-8")) or {}
            return list(data.get("blacklist", []))
    except Exception as exc:
        logger.error("blacklist load failed: %s", exc)
    return []


def _grade(score: float) -> str:
    """점수 → 등급 변환."""
    if score >= 90:
        return "S"
    elif score >= 80:
        return "A"
    elif score >= 70:
        return "B"
    return "C"


class ScannerRanker:
    """
    심볼별 feature 딕셔너리를 받아 내림차순 랭킹 반환.
    - blacklist 제외
    - total_score 70점 미만 제외
    - 등급: S(90+) / A(80+) / B(70+)
    """

    def rank_all(
        self, features: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        features: {symbol: compute_all_features 반환값}
        반환: [{"symbol", "score", "grade", "features"}, ...] 내림차순
        """
        blacklist = _load_blacklist()
        ranked: List[Dict[str, Any]] = []

        for symbol, feat in features.items():
            if symbol in blacklist:
                logger.info("ranker skip blacklisted symbol=%s", symbol)
                continue
            score = float(feat.get("total_score", 0.0))
            if score < _MIN_SCORE:
                continue
            ranked.append({
                "symbol":   symbol,
                "score":    round(score, 4),
                "grade":    _grade(score),
                "features": feat,
            })

        ranked.sort(key=lambda x: x["score"], reverse=True)
        for idx, item in enumerate(ranked):
            if idx == 0:
                item["grade"] = "A"   # TOP1 → A (entry_score +10점)
            elif idx == 1:
                item["grade"] = "B"   # TOP2 → B (entry_score +5점)
            else:
                item["grade"] = "C"   # TOP3 이하 → C (entry_score +0점)
        logger.info(
            "ranker result count=%d top=%s",
            len(ranked),
            [r["symbol"] for r in ranked[:3]],
        )
        return ranked
