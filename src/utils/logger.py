from __future__ import annotations

import logging
import os
from datetime import datetime, timezone


def get_logger(name: str, log_dir: str = "app") -> logging.Logger:
    """
    파일 + 콘솔 핸들러 Logger 반환.
    로그 경로: logs/{log_dir}/YYYY-MM-DD.log
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "[%(asctime)s UTC] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    try:
        log_path = os.path.join("logs", log_dir)
        os.makedirs(log_path, exist_ok=True)
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        file_path = os.path.join(log_path, f"{date_str}.log")
        fh = logging.FileHandler(file_path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception:
        pass

    return logger

