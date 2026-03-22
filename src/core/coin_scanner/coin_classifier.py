from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger("scanner.classifier")

# config에서 읽는 임계값 기본값
_HIGH_BETA_THRESHOLD = 1.2
_INDEPENDENT_CORRELATION_MAX = 0.6
_FUNDING_EXTREME_THRESHOLD = 0.0005
_RANGE_PLAY_ATR_RATIO = 0.7


def _safe_returns(prices: List[float]) -> List[float]:
    """가격 리스트 → 수익률 리스트 (log return)."""
    if len(prices) < 2:
        return []
    returns = []
    for i in range(1, len(prices)):
        if prices[i - 1] > 0:
            returns.append(math.log(prices[i] / prices[i - 1]))
        else:
            returns.append(0.0)
    return returns


class CoinClassifier:
    """
    각 코인을 유형별로 분류한다.
    우선순위: CORE → FUNDING_EXTREME → HIGH_BETA → INDEPENDENT → RANGE_PLAY
    """

    def __init__(self, config: Optional[Any] = None) -> None:
        self._config = config
        self._high_beta_threshold = (
            float(getattr(config, "high_beta_threshold", _HIGH_BETA_THRESHOLD))
            if config else _HIGH_BETA_THRESHOLD
        )
        self._independent_corr_max = (
            float(getattr(config, "independent_correlation_max", _INDEPENDENT_CORRELATION_MAX))
            if config else _INDEPENDENT_CORRELATION_MAX
        )
        self._funding_extreme_threshold = (
            float(getattr(config, "funding_extreme_threshold", _FUNDING_EXTREME_THRESHOLD))
            if config else _FUNDING_EXTREME_THRESHOLD
        )

    def classify_all(
        self,
        symbols: List[str],
        btc_returns: List[float],
        market_states: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, str]:
        result: Dict[str, str] = {}
        market_states = market_states or {}

        for symbol in symbols:
            try:
                result[symbol] = self._classify_one(
                    symbol, btc_returns, market_states.get(symbol, {})
                )
            except Exception as exc:
                logger.error(
                    "classifier failed symbol=%s error=%s", symbol, exc
                )
                result[symbol] = "RANGE_PLAY"

        logger.info("coin_classifier result %s", result)
        return result

    def _classify_one(
        self,
        symbol: str,
        btc_returns: List[float],
        market_state: Dict[str, Any],
    ) -> str:
        if symbol in ("BTCUSDT", "ETHUSDT"):
            return "CORE"

        funding_rate = float(market_state.get("funding_rate") or 0.0)
        if abs(funding_rate) >= self._funding_extreme_threshold:
            return "FUNDING_EXTREME"

        klines_1h: List[Dict[str, Any]] = market_state.get("klines_1h") or []
        coin_closes = [float(k.get("close", 0)) for k in klines_1h if k.get("close")]
        coin_returns = _safe_returns(coin_closes)

        min_len = min(len(coin_returns), len(btc_returns))

        if min_len >= 10:
            cr = np.array(coin_returns[-min_len:])
            br = np.array(btc_returns[-min_len:])
            btc_var = float(np.var(br))
            if btc_var > 1e-12:
                beta = float(np.cov(cr, br)[0, 1] / btc_var)
                if beta >= self._high_beta_threshold:
                    return "HIGH_BETA"

            corr_matrix = np.corrcoef(cr, br)
            correlation = float(corr_matrix[0, 1]) if corr_matrix.shape == (2, 2) else 1.0
            if not math.isfinite(correlation):
                correlation = 1.0
            if correlation < self._independent_corr_max:
                return "INDEPENDENT"

        return "RANGE_PLAY"

    def compute_beta(
        self,
        symbol: str,
        btc_returns: List[float],
        market_state: Dict[str, Any],
    ) -> float:
        try:
            klines_1h: List[Dict[str, Any]] = market_state.get("klines_1h") or []
            coin_closes = [float(k.get("close", 0)) for k in klines_1h if k.get("close")]
            coin_returns = _safe_returns(coin_closes)
            min_len = min(len(coin_returns), len(btc_returns))
            if min_len < 10:
                return 0.0
            cr = np.array(coin_returns[-min_len:])
            br = np.array(btc_returns[-min_len:])
            btc_var = float(np.var(br))
            if btc_var < 1e-12:
                return 0.0
            return float(np.cov(cr, br)[0, 1] / btc_var)
        except Exception as exc:
            logger.error("compute_beta failed symbol=%s error=%s", symbol, exc)
            return 0.0
