from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


@dataclass(frozen=True)
class Settings:
    ib_host: str = os.getenv("IB_HOST", "127.0.0.1")
    ib_port: int = _int("IB_PORT", 7497)
    ib_client_id: int = _int("IB_CLIENT_ID", 17)
    ib_account: str = os.getenv("IB_ACCOUNT", "").strip()
    paper_account_only: bool = _bool("PAPER_ACCOUNT_ONLY", True)

    dry_run: bool = _bool("DRY_RUN", True)
    auto_trading_enabled: bool = _bool("AUTO_TRADING_ENABLED", False)

    watchlist: tuple[str, ...] = tuple(
        symbol.strip().upper()
        for symbol in os.getenv(
            "WATCHLIST", "ARM,NVDA,AMD,TSLA,META,AAPL,MSFT,AMZN,QQQ,SPY"
        ).split(",")
        if symbol.strip()
    )
    bar_size: str = os.getenv("BAR_SIZE", "10 mins")
    history_duration: str = os.getenv("HISTORY_DURATION", "5 D")
    scan_interval_seconds: int = _int("SCAN_INTERVAL_SECONDS", 60)
    use_rth: bool = _bool("USE_RTH", True)
    market_data_type: int = _int("MARKET_DATA_TYPE", 3)

    risk_per_trade: float = _float("RISK_PER_TRADE", 0.005)
    max_position_value_pct: float = _float("MAX_POSITION_VALUE_PCT", 0.20)
    max_open_positions: int = _int("MAX_OPEN_POSITIONS", 3)
    max_daily_loss_pct: float = _float("MAX_DAILY_LOSS_PCT", 0.02)
    atr_stop_multiplier: float = _float("ATR_STOP_MULTIPLIER", 1.5)
    reward_risk_ratio: float = _float("REWARD_RISK_RATIO", 2.0)
    min_signal_score: int = _int("MIN_SIGNAL_SCORE", 80)

    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    database_path: Path = Path(os.getenv("DATABASE_PATH", "tradebot.db"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

    def validate(self) -> None:
        if not 0 < self.risk_per_trade <= 0.02:
            raise ValueError("RISK_PER_TRADE must be between 0 and 0.02")
        if not 0 < self.max_daily_loss_pct <= 0.10:
            raise ValueError("MAX_DAILY_LOSS_PCT must be between 0 and 0.10")
        if self.max_open_positions < 1:
            raise ValueError("MAX_OPEN_POSITIONS must be at least 1")
        if self.paper_account_only and self.ib_port != 7497:
            raise ValueError("Paper-only mode expects TWS paper port 7497")
        if self.auto_trading_enabled and self.dry_run:
            raise ValueError("AUTO_TRADING_ENABLED and DRY_RUN cannot both be true")


settings = Settings()
