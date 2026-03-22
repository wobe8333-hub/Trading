from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

from src.utils.file_utils import load_yaml
from src.utils.validators import (
    ValidationError,
    validate_modes,
    validate_numeric_keys,
    validate_required_keys,
)


SYSTEM_CONFIG_PATH = Path("config") / "system_config.yaml"
RISK_STAGE_CONFIG_PATH = Path("config") / "risk_stage_config.yaml"


@dataclass(frozen=True)
class Config:
    capital_start: float
    capital_target: float
    leverage: float

    max_capital_usage: float
    max_capital_usage_a_plus: float

    daily_loss_limit_usd: float
    max_consecutive_losses: int

    scanner_top_n: int
    scanner_interval_seconds: int

    entry_score_min: float
    entry_score_a: float
    entry_score_a_plus: float
    entry_score_high_risk_min: float

    timeframe_main: str
    timeframe_confirm_fast: str
    timeframe_confirm_slow: str

    paper_mode: bool
    live_mode: bool

    risk_stage: str
    risk_pct: float
    # trade_sessions 설정은 SSOT 기준 ["LONDON","NY","OVERLAP"] 목록
    # 이후 세션 필터에서 사용된다.
    trade_sessions: Tuple[str, ...]

    bybit_api_key: str
    bybit_api_secret: str
    bybit_testnet: bool


_CONFIG_SINGLETON: Config | None = None


def _detect_risk_stage(
    capital: float, stages_list: list
) -> Tuple[str, float]:
    """stages 리스트에서 equity_min <= capital < equity_max 조건으로 Stage 탐색."""
    for stage in stages_list:
        low  = float(stage.get("equity_min", 0))
        high = float(stage.get("equity_max", float("inf")))
        risk = stage.get("risk_pct_per_trade")
        sid  = stage.get("id")
        if risk is not None and low <= capital < high:
            return f"Stage{sid}", float(risk)
    last = stages_list[-1]
    return f"Stage{last['id']}", float(last["risk_pct_per_trade"])


def _load_config() -> Config:
    system_cfg = load_yaml(SYSTEM_CONFIG_PATH)

    required_keys = [
        "capital_start",
        "capital_target",
        "leverage",
        "max_capital_usage",
        "max_capital_usage_a_plus",
        "daily_loss_limit_usd",
        "max_consecutive_losses",
        "scanner_top_n",
        "scanner_interval_seconds",
        "entry_score_min",
        "entry_score_a",
        "entry_score_a_plus",
        "timeframe_main",
        "timeframe_confirm_fast",
        "timeframe_confirm_slow",
        "paper_mode",
        "live_mode",
        "trade_sessions",
        "bybit_api_key",
        "bybit_api_secret",
        "bybit_testnet",
    ]
    validate_required_keys(system_cfg, required_keys)

    numeric_keys = [
        "capital_start",
        "capital_target",
        "leverage",
        "max_capital_usage",
        "max_capital_usage_a_plus",
        "daily_loss_limit_usd",
        "max_consecutive_losses",
        "scanner_top_n",
        "scanner_interval_seconds",
        "entry_score_min",
        "entry_score_a",
        "entry_score_a_plus",
    ]
    validate_numeric_keys(system_cfg, numeric_keys)

    paper_mode = bool(system_cfg["paper_mode"])
    live_mode = bool(system_cfg["live_mode"])
    validate_modes(paper_mode, live_mode)

    risk_cfg   = load_yaml(RISK_STAGE_CONFIG_PATH)
    stages_raw = risk_cfg.get("stages", [])
    if not stages_raw:
        raise ValidationError("risk_stage_config.yaml: 'stages' list is empty")
    stage_name, risk_pct = _detect_risk_stage(
        float(system_cfg["capital_start"]), stages_raw
    )

    return Config(
        capital_start=float(system_cfg["capital_start"]),
        capital_target=float(system_cfg["capital_target"]),
        leverage=float(system_cfg["leverage"]),
        max_capital_usage=float(system_cfg["max_capital_usage"]),
        max_capital_usage_a_plus=float(system_cfg["max_capital_usage_a_plus"]),
        daily_loss_limit_usd=float(system_cfg["daily_loss_limit_usd"]),
        max_consecutive_losses=int(system_cfg["max_consecutive_losses"]),
        scanner_top_n=int(system_cfg["scanner_top_n"]),
        scanner_interval_seconds=int(system_cfg["scanner_interval_seconds"]),
        entry_score_min=float(system_cfg["entry_score_min"]),
        entry_score_a=float(system_cfg["entry_score_a"]),
        entry_score_a_plus=float(system_cfg["entry_score_a_plus"]),
        entry_score_high_risk_min=float(
            system_cfg.get("entry_score_high_risk_min", 80)
        ),
        timeframe_main=str(system_cfg["timeframe_main"]),
        timeframe_confirm_fast=str(system_cfg["timeframe_confirm_fast"]),
        timeframe_confirm_slow=str(system_cfg["timeframe_confirm_slow"]),
        paper_mode=paper_mode,
        live_mode=live_mode,
        risk_stage=stage_name,
        risk_pct=risk_pct,
        trade_sessions=tuple(system_cfg["trade_sessions"]),
        bybit_api_key=str(system_cfg.get("bybit_api_key", "")),
        bybit_api_secret=str(system_cfg.get("bybit_api_secret", "")),
        bybit_testnet=bool(system_cfg.get("bybit_testnet", False)),
    )


def get_config() -> Config:
    """글로벌 Config 싱글톤을 반환한다."""
    global _CONFIG_SINGLETON
    if _CONFIG_SINGLETON is None:
        _CONFIG_SINGLETON = _load_config()
    return _CONFIG_SINGLETON

