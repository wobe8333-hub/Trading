from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


class FileLoadError(Exception):
    """설정/리소스 파일 로딩 오류."""


def load_yaml(path: str | Path) -> Dict[str, Any]:
    """YAML 파일을 로드해 dict로 반환한다."""
    p = Path(path)
    if not p.is_file():
        raise FileLoadError(f"YAML file not found: {p}")

    try:
        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        raise FileLoadError(f"Failed to parse YAML file: {p}") from exc

    if not isinstance(data, dict):
        raise FileLoadError(f"YAML root must be a mapping: {p}")

    return data

