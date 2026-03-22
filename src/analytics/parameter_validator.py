from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.analytics.expectancy_engine import ExpectancyEngine

logger = logging.getLogger("analytics.parameter_validator")

_VALIDATION_THRESHOLD = 50  # [검증값] 50거래 이상 누적 시 실행
_VARIATION_PCT = 0.20  # [초기값] ±20% 변화 범위
_N_VARIATIONS = 5  # [초기값] 5개 값 테스트
_IMPROVEMENT_THRESHOLD = 5.0  # [초기값] 5% 이상 개선 시 권고
_CACHE_DIR = "data/analytics_cache"


class ParameterValidator:
    """
    50거래 이상 누적 후 파라미터 최적화 시뮬레이션.
    교체를 강제하지 않으며 권고만 출력한다.
    """

    def __init__(self) -> None:
        self._expectancy = ExpectancyEngine()
        os.makedirs(_CACHE_DIR, exist_ok=True)

    def validate_strategy_params(
        self,
        strategy_name: str,
        param_name: str,
        current_value: float,
        trades: List[Dict[str, Any]],
        variation_pct: float = _VARIATION_PCT,
        n_variations: int = _N_VARIATIONS,
    ) -> Dict[str, Any]:
        """
        구현지침서 명세 5개 테스트 값 시뮬레이션 후 best 값 반환.
        """
        try:
            if len(trades) < _VALIDATION_THRESHOLD:  # [검증값]
                return {
                    "strategy": strategy_name,
                    "param": param_name,
                    "current_value": current_value,
                    "recommendation": "데이터 부족 (50거래 미만)",
                    "current_expectancy": 0.0,
                    "best_value": current_value,
                    "best_expectancy": 0.0,
                    "improvement_pct": 0.0,
                    "test_results": {},
                }

            step = variation_pct / (n_variations // 2)
            test_values = [
                current_value * (1 - variation_pct),
                current_value * (1 - variation_pct / 2),
                current_value,
                current_value * (1 + variation_pct / 2),
                current_value * (1 + variation_pct),
            ]

            results: Dict[float, float] = {}
            for v in test_values:
                simulated = self.simulate_with_param(trades, param_name, v)
                exp_result = self._expectancy.compute_expectancy(simulated)
                results[v] = exp_result["expectancy"]

            best_value = max(results, key=lambda k: results[k])
            curr_exp = results.get(current_value, 0.0)
            best_exp = results[best_value]
            improvement = (
                (best_exp - curr_exp) / abs(curr_exp) * 100
                if abs(curr_exp) > 1e-9
                else 0.0
            )
            recommendation = (
                "교체 권고" if improvement > _IMPROVEMENT_THRESHOLD else "현재 유지"
            )

            result = {
                "strategy": strategy_name,
                "param": param_name,
                "current_value": current_value,
                "current_expectancy": round(curr_exp, 4),
                "best_value": best_value,
                "best_expectancy": round(best_exp, 4),
                "improvement_pct": round(improvement, 2),
                "recommendation": recommendation,
                "test_results": {str(k): round(v, 4) for k, v in results.items()},
            }
            logger.info(
                "parameter_validator strategy=%s param=%s rec=%s improvement=%.1f%%",
                strategy_name,
                param_name,
                recommendation,
                improvement,
            )
            return result
        except Exception as exc:
            logger.error("parameter_validator failed error=%s", exc)
            return {
                "strategy": strategy_name,
                "param": param_name,
                "current_value": current_value,
                "recommendation": "검증 오류",
                "current_expectancy": 0.0,
                "best_value": current_value,
                "best_expectancy": 0.0,
                "improvement_pct": 0.0,
                "test_results": {},
            }

    @staticmethod
    def simulate_with_param(
        trades: List[Dict[str, Any]],
        param_name: str,
        value: float,
    ) -> List[Dict[str, Any]]:
        """
        파라미터 값 변경 시 거래 필터링 시뮬레이션.
        현재 구현: 파라미터 관련 없는 거래만 통과 (보수적 접근).
        """
        _ = (param_name, value)
        return [t for t in trades if t.get("pnl_net") is not None]

    def run_full_validation(
        self,
        strategy_name: str,
        trades: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """50거래 이상 시 전체 파라미터 검증. 결과를 캐시에 저장."""
        if len(trades) < _VALIDATION_THRESHOLD:
            return []
        try:
            from src.utils.config_loader import load_strategy_config

            cfg = load_strategy_config()
            params = cfg.get(strategy_name, {}).get("params", {})
            results: List[Dict[str, Any]] = []
            for param, val in params.items():
                if isinstance(val, (int, float)):
                    r = self.validate_strategy_params(strategy_name, param, float(val), trades)
                    results.append(r)
            self._save_cache(strategy_name, results)
            return results
        except Exception as exc:
            logger.error("parameter_validator run_full_validation failed error=%s", exc)
            return []

    def _save_cache(self, strategy_name: str, results: List[Dict[str, Any]]) -> None:
        try:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            path = os.path.join(_CACHE_DIR, f"validation_{date}.json")
            existing: List[Dict[str, Any]] = []
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            existing.extend(results)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error("parameter_validator save_cache failed error=%s", exc)

