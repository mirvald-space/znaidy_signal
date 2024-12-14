from dataclasses import dataclass
from typing import List, Optional

from environs import Env


@dataclass
class TgBot:
    token: str


@dataclass
class WebhookConfig:
    host: str
    port: int
    path: str

    @property
    def url(self) -> str:
        return f"{self.host}{self.path}"


@dataclass
class TradingConfig:
    symbols: List[str]
    update_interval: int
    timeframe: str = "1h"
    risk_percent: float = 1.0
    balance: float = 1000.0
    rsi_period: int = 14
    short_sma: int = 5
    long_sma: int = 20
    min_volume: float = 1000.0
    min_volatility: float = 0.001
    max_volatility: float = 0.05


@dataclass
class LoggingConfig:
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format: str = "%Y-%m-%d %H:%M:%S"
    log_dir: str = "logs"
    analytics_dir: str = "analytics"


@dataclass
class Config:
    tg_bot: TgBot
    webhook: WebhookConfig
    trading: TradingConfig
    logging: LoggingConfig


def load_config(path: Optional[str] = None) -> Config:
    """
    Загрузка конфигурации из переменных окружения или .env файла
    Args:
        path: Путь к .env файлу
    Returns:
        Config: Объект конфигурации
    """
    env = Env()
    env.read_env(path)

    return Config(
        tg_bot=TgBot(
            token=env("BOT_TOKEN"),
        ),
        webhook=WebhookConfig(
            host=env("WEBHOOK_URL", "https://your-app.onrender.com"),
            port=env.int("PORT", 8000),  # Changed to match ngrok port
            path=f"/webhook/{env('BOT_TOKEN')}"
        ),
        trading=TradingConfig(
            symbols=env.list("TRADING_SYMBOLS",
                             ["BTCUSDT", "ETHUSDT", "SOLUSDT",
                                 "BNBUSDT", "ADAUSDT"],
                             subcast=str),
            update_interval=env.int("UPDATE_INTERVAL", 50),
            timeframe=env("TIMEFRAME", "1h"),
            risk_percent=env.float("RISK_PERCENT", 1.0),
            balance=env.float("BALANCE", 1000.0),
            rsi_period=env.int("RSI_PERIOD", 14),
            short_sma=env.int("SHORT_SMA", 5),
            long_sma=env.int("LONG_SMA", 20),
            min_volume=env.float("MIN_VOLUME", 1000.0),
            min_volatility=env.float("MIN_VOLATILITY", 0.001),
            max_volatility=env.float("MAX_VOLATILITY", 0.05)
        ),
        logging=LoggingConfig(
            level=env("LOG_LEVEL", "INFO"),
            format=env("LOG_FORMAT",
                       "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            date_format=env("LOG_DATE_FORMAT", "%Y-%m-%d %H:%M:%S"),
            log_dir=env("LOG_DIR", "logs"),
            analytics_dir=env("ANALYTICS_DIR", "analytics")
        )
    )
