from __future__ import annotations

import logging
import sys

from src.utils.config_loader import ConfigManager
from src.app.trading_loop import TradingLoop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("app.main")


def main() -> None:
    cfg_mgr = ConfigManager()
    cfg = cfg_mgr.load_system_config()

    paper_mode = cfg.get("paper_mode", True)
    live_mode = cfg.get("live_mode", False)

    if paper_mode:
        print("[PAPER MODE] 실제 주문 없이 실행합니다.")

    if live_mode:
        confirm = input("LIVE MODE 진입합니다. 계속하려면 'YES' 입력: ")
        if confirm.strip() != "YES":
            print("취소됨.")
            sys.exit(0)

    loop = TradingLoop(paper_mode=paper_mode)
    loop.run()


if __name__ == "__main__":
    main()

