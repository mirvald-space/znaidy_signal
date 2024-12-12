# bot.py
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
from trading.trading_system import TradingSystem
from trading.signal_formatter import format_signal_message
from config import Config, load_config
from utils.logger import setup_logger

# Настройка логирования
logger = setup_logger()

# Символы для мониторинга
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
UPDATE_INTERVAL = 300  # 5 минут

# Хранение подписчиков (в реальном приложении лучше использовать базу данных)
subscribers = set()

# Инициализация бота
config = load_config()
bot = Bot(token=config.tg_bot.token)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    subscribers.add(message.from_user.id)
    await message.answer(
        "👋 Привет! Я бот для отслеживания криптовалютных сигналов.\n"
        "Теперь вы будете получать уведомления о торговых сигналах.\n\n"
        "Доступные команды:\n"
        "/start - Подписаться на сигналы\n"
        "/stop - Отписаться от сигналов\n"
        "/status - Текущий статус анализа\n"
        "/symbols - Список отслеживаемых символов"
    )

@dp.message(Command("stop"))
async def cmd_stop(message: Message):
    subscribers.discard(message.from_user.id)
    await message.answer("Вы отписались от уведомлений. Используйте /start чтобы подписаться снова.")

@dp.message(Command("status"))
async def cmd_status(message: Message):
    status_message = [
        "📊 Текущий статус системы:",
        f"Активных подписчиков: {len(subscribers)}",
        f"Отслеживаемые пары: {', '.join(SYMBOLS)}",
        f"Интервал обновления: {UPDATE_INTERVAL} секунд",
    ]
    await message.answer("\n".join(status_message))

@dp.message(Command("symbols"))
async def cmd_symbols(message: Message):
    symbols_message = [
        "📈 Отслеживаемые торговые пары:",
        ""
    ]
    for symbol in SYMBOLS:
        symbols_message.append(f"• {symbol}")
    await message.answer("\n".join(symbols_message))

async def send_signals():
    """Отправка сигналов подписчикам"""
    while True:
        try:
            logger.info("Starting signal analysis cycle")
            
            for symbol in SYMBOLS:
                try:
                    trader = TradingSystem(symbol)
                    analysis = trader.analyze()
                    
                    if not analysis:
                        logger.warning(f"No analysis results for {symbol}")
                        continue
                        
                    # Форматируем сообщение
                    message = format_signal_message(analysis)
                    
                    # Отправляем только если есть сигналы или подходит для торговли
                    if analysis['signals'] or analysis['context']['suitable_for_trading']:
                        logger.info(f"Sending signals for {symbol} to {len(subscribers)} subscribers")
                        for user_id in subscribers:
                            try:
                                await bot.send_message(user_id, message)
                                await asyncio.sleep(0.1)  # Небольшая задержка между отправками
                            except Exception as e:
                                logger.error(f"Error sending message to {user_id}: {e}")
                    else:
                        logger.info(f"No significant signals for {symbol}")
                        
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")
                    continue
                    
            logger.info(f"Analysis cycle completed. Waiting {UPDATE_INTERVAL} seconds")
            await asyncio.sleep(UPDATE_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error in send_signals: {e}")
            await asyncio.sleep(60)  # Ждем минуту перед повторной попыткой