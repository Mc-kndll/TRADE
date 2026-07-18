"""Command-line entry point for the paper-trading bot."""

from __future__ import annotations

import argparse
import json
import logging
from logging.handlers import RotatingFileHandler

from .config import Settings, settings
from .database import Database


def configure_logging(config: Settings) -> None:
    config.log_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
    )
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    file_handler = RotatingFileHandler(
        config.log_path, maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        handlers=[console, file_handler],
        force=True,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IBKR TWS paper-trading bot")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Run exactly one scan cycle")
    mode.add_argument("--status", action="store_true", help="Show local persisted status")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    configure_logging(settings)
    try:
        settings.validate()
        if args.status:
            status = Database(settings.database_path).status_summary()
            print(json.dumps(status, indent=2, default=str))
            return 0
        from .engine import TradingEngine

        TradingEngine(settings).start(once=args.once)
        return 0
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Stopped by user")
        return 130
    except Exception:
        logging.getLogger(__name__).exception("Fatal application error")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
