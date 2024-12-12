# main.py
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from config import load_config
from trading.signal_formatter import format_signal_message
from trading.trading_system import TradingSystem
from utils.analytics_logger import AnalyticsLogger

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
config = load_config()
WEBHOOK_HOST = os.environ.get("WEBHOOK_URL", "https://your-app.onrender.com")
WEBHOOK_PATH = f"/webhook/{config.tg_bot.token}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
PORT = int(os.environ.get("PORT", 8080))

# Символы для мониторинга
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
UPDATE_INTERVAL = 300  # 5 минут

# Хранение подписчиков
subscribers = set()

# Инициализация бота
bot = Bot(token=config.tg_bot.token)
dp = Dispatcher()
