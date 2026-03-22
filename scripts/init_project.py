from __future__ import annotations

import os
import yaml


def init_project() -> None:
    dirs = [
        "config",
        "data/market_cache",
        "data/scanner_cache",
        "data/analytics_cache",
        "data/trade_history",
        "data/model_features",
        "data/training_sets",
        "data/replay",
        "logs/app",
        "logs/orders",
        "logs/errors",
        "logs/scanner",
        "logs/analytics",
        "logs/kill_switch",
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)

    blacklist_path = "config/symbol_blacklist.yaml"
    if not os.path.exists(blacklist_path):
        with open(blacklist_path, "w", encoding="utf-8") as f:
            yaml.dump({"blacklist": []}, f)

    print("프로젝트 디렉토리 초기화 완료")
    for d in dirs:
        print(f"  {d}/")


if __name__ == "__main__":
    init_project()

