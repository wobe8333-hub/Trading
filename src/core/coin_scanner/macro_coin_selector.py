from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger("scanner.macro_selector")

_MIN_SCORE: Dict[str, Dict[str, float]] = {
    "BULL": {
        "CORE":             25.0,
        "HIGH_BETA":        25.0,
        "RANGE_PLAY":       25.0,
        "INDEPENDENT":      25.0,
        "FUNDING_EXTREME":  25.0,
    },
    "BEAR": {
        "CORE":             25.0,
        "HIGH_BETA":        25.0,
        "RANGE_PLAY":       25.0,
        "INDEPENDENT":      25.0,
        "FUNDING_EXTREME":  25.0,
    },
    "NEUTRAL": {
        "CORE":             25.0,
        "HIGH_BETA":        25.0,
        "RANGE_PLAY":       25.0,
        "INDEPENDENT":      25.0,
        "FUNDING_EXTREME":  25.0,
    },
    "EXPANSION": {
        "CORE":             25.0,
        "HIGH_BETA":        25.0,
        "RANGE_PLAY":       25.0,
        "INDEPENDENT":      25.0,
        "FUNDING_EXTREME":  25.0,
    },
}

_TARGET_COMPOSITION: Dict[str, List[str]] = {
    "BULL":      ["CORE", "HIGH_BETA", "HIGH_BETA"],
    "BEAR":      ["CORE", "HIGH_BETA", "INDEPENDENT"],
    "NEUTRAL":   ["CORE", "RANGE_PLAY", "INDEPENDENT"],
    "EXPANSION": ["CORE", "HIGH_BETA", "INDEPENDENT"],
}

_FALLBACK_TYPE = "INDEPENDENT"


def _filter_by_type(
    ranked_list: List[Dict[str, Any]],
    coin_types: Dict[str, str],
    target_type: str,
    min_score: float,
) -> List[Dict[str, Any]]:
    return [
        item for item in ranked_list
        if coin_types.get(item["symbol"]) == target_type
        and item["score"] >= min_score
    ]


class MacroCoinSelector:
    def select_top3(
        self,
        ranked_list: List[Dict[str, Any]],
        coin_types: Dict[str, str],
        macro_state: str,
    ) -> List[Dict[str, Any]]:
        if macro_state == "RISK_OFF":
            logger.warning("macro_selector RISK_OFF — returning empty TOP3")
            return []

        target_types = _TARGET_COMPOSITION.get(macro_state)
        if target_types is None:
            logger.error(
                "macro_selector unknown macro_state=%s — fallback NEUTRAL",
                macro_state,
            )
            target_types = _TARGET_COMPOSITION["NEUTRAL"]
            macro_state = "NEUTRAL"

        min_scores = _MIN_SCORE.get(macro_state, {})
        selected: List[Dict[str, Any]] = []
        used_symbols: set[str] = set()

        for target_type in target_types:
            min_score = min_scores.get(target_type, 25.0)
            candidates = _filter_by_type(
                ranked_list, coin_types, target_type, min_score
            )
            candidates = [c for c in candidates if c["symbol"] not in used_symbols]

            if candidates:
                chosen = candidates[0]
                entry = {**chosen, "coin_type": target_type}
                selected.append(entry)
                used_symbols.add(chosen["symbol"])
            else:
                if macro_state == "BULL" and target_type == "HIGH_BETA":
                    fallback_min = min_scores.get(_FALLBACK_TYPE, 25.0)
                    fallback_cands = _filter_by_type(
                        ranked_list, coin_types, _FALLBACK_TYPE, fallback_min
                    )
                    fallback_cands = [
                        c for c in fallback_cands
                        if c["symbol"] not in used_symbols
                    ]
                    if fallback_cands:
                        chosen = fallback_cands[0]
                        entry = {**chosen, "coin_type": _FALLBACK_TYPE}
                        selected.append(entry)
                        used_symbols.add(chosen["symbol"])
                        logger.info(
                            "macro_selector HIGH_BETA slot replaced by INDEPENDENT symbol=%s",
                            chosen["symbol"],
                        )
                    else:
                        logger.info(
                            "macro_selector slot skipped type=%s macro=%s",
                            target_type, macro_state,
                        )
                else:
                    logger.info(
                        "macro_selector slot skipped type=%s macro=%s",
                        target_type, macro_state,
                    )

        logger.info(
            "macro_selector TOP%d macro=%s symbols=%s",
            len(selected),
            macro_state,
            [r["symbol"] for r in selected],
        )
        return selected
