from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


CONFIG_DIR             = Path("config")
SYSTEM_CONFIG_PATH     = CONFIG_DIR / "system_config.yaml"
RISK_STAGE_CONFIG_PATH = CONFIG_DIR / "risk_stage_config.yaml"
STRATEGY_CONFIG_PATH   = CONFIG_DIR / "strategy_config.yaml"


class ConfigError(Exception):
    """설정 로딩 관련 예외."""


_REQUIRED_SYSTEM_KEYS: List[str] = [
    "capital_start",
    "capital_target",
    "leverage",
    "bybit_api_key",
    "bybit_api_secret",
    "paper_mode",
    "live_mode",
    "entry_score_min",
]


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Failed to parse YAML: {path}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"YAML root must be a mapping: {path}")
    return data


def _apply_env_overrides(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """환경 변수 오버라이드 (BYBIT_API_KEY, BYBIT_API_SECRET, PAPER_MODE)."""
    if "BYBIT_API_KEY" in os.environ:
        cfg["bybit_api_key"] = os.environ["BYBIT_API_KEY"]
    if "BYBIT_API_SECRET" in os.environ:
        cfg["bybit_api_secret"] = os.environ["BYBIT_API_SECRET"]
    if "PAPER_MODE" in os.environ:
        val = os.environ["PAPER_MODE"].strip().lower()
        cfg["paper_mode"] = val not in ("false", "0", "no")
    return cfg


def load_system_config() -> Dict[str, Any]:
    """
    config/system_config.yaml 로드 후 환경변수 오버라이드 적용.
    필수 키 누락 시 ValueError 발생.
    """
    cfg = _load_yaml(SYSTEM_CONFIG_PATH)
    cfg = _apply_env_overrides(cfg)
    missing = [k for k in _REQUIRED_SYSTEM_KEYS if k not in cfg]
    if missing:
        raise ValueError(f"Missing required config keys: {', '.join(missing)}")
    return cfg


def load_stage_config() -> List[Dict[str, Any]]:
    """config/risk_stage_config.yaml 로드 → stages 리스트 반환."""
    data = _load_yaml(RISK_STAGE_CONFIG_PATH)
    stages = data.get("stages")
    if not isinstance(stages, list):
        raise ConfigError("risk_stage_config.yaml must have a 'stages' list")
    return stages


def load_strategy_config() -> Dict[str, Any]:
    """config/strategy_config.yaml 로드 → strategies dict 반환."""
    data = _load_yaml(STRATEGY_CONFIG_PATH)
    strategies = data.get("strategies")
    if not isinstance(strategies, dict):
        raise ConfigError("strategy_config.yaml must have a 'strategies' dict")
    return strategies


def get_stage_for_equity(equity: float) -> Dict[str, Any]:
    """
    현재 계좌 잔고에 맞는 Stage 설정 반환.
    equity_min <= equity < equity_max 조건으로 매칭.
    매칭 없으면 마지막 stage 반환.
    """
    stages = load_stage_config()
    for stage in stages:
        low  = float(stage.get("equity_min", 0))
        high = float(stage.get("equity_max", float("inf")))
        if low <= equity < high:
            return stage
    return stages[-1]


class ConfigManager:
    """
    싱글톤 설정 관리자.
    최초 1회 로드 후 캐시. reload()로 강제 재로드 가능.
    """

    _instance: Optional["ConfigManager"] = None
    _cache: Optional[Dict[str, Any]] = None

    def __new__(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _load(self) -> None:
        self._cache = load_system_config()

    def get(self, key: str, default: Any = None) -> Any:
        if self._cache is None:
            self._load()
        return self._cache.get(key, default)  # type: ignore[union-attr]

    def reload(self) -> None:
        """설정을 강제 재로드한다."""
        self._load()

    def all(self) -> Dict[str, Any]:
        if self._cache is None:
            self._load()
        return dict(self._cache)  # type: ignore[arg-type]

    # ── STEP 20/21 호환 ──────────────────────────────────────────
    # TradingLoop가 ConfigManager.get_config()를 호출하며,
    # MarketDataManager는 src.app.config_loader.Config dataclass를 기대한다.
    def get_config(self) -> Any:
        """
        호환용: src.app.config_loader.get_config()의 반환값을 그대로 제공.
        """
        from src.app.config_loader import get_config as _get_app_config

        return _get_app_config()

    # ── STEP 13/14 호환 래퍼 ──────────────────────────────────
    # STEP 13/14 코드가 ConfigManager().load_system_config() 형태를 호출한다.
    def load_system_config(self) -> Dict[str, Any]:
        """호환용 래퍼: system_config.yaml 로드."""
        return load_system_config()

    def load_stage_config(self) -> List[Dict[str, Any]]:
        """호환용 래퍼: risk_stage_config.yaml 로드."""
        return load_stage_config()

