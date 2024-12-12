# background_tasks.py

import asyncio
import logging
from datetime import datetime
from string import Template
from typing import Set

from aiogram import Bot

from trading.signal_formatter import format_signal_message
from trading.trading_system import TradingSystem
from utils.analytics_logger import AnalyticsLogger

logger = logging.getLogger(__name__)


class BackgroundTasks:
    def __init__(self, bot: Bot, symbols: list, update_interval: int, subscribers: Set[int]):
        self.bot = bot
        self.symbols = symbols
        self.update_interval = update_interval
        self.subscribers = subscribers
        self.tasks = {}
        self.is_running = False
        self.analytics_logger = AnalyticsLogger()

    async def start(self):
        """Запуск фоновых задач"""
        if not self.is_running:
            self.is_running = True
            self.tasks['signal_analysis'] = asyncio.create_task(
                self.signal_analysis_loop())
            self.tasks['data_cleanup'] = asyncio.create_task(
                self.data_cleanup_loop())
            logger.info("Background tasks started")

    async def stop(self):
        """Остановка фоновых задач"""
        self.is_running = False
        for task_name, task in self.tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                logger.info("Task {} stopped".format(task_name))
        self.tasks.clear()
        logger.info("All background tasks stopped")

    async def signal_analysis_loop(self):
        """Основной цикл анализа сигналов"""
        while self.is_running:
            try:
                logger.info("Starting signal analysis cycle")
                start_time = datetime.now()

                for symbol in self.symbols:
                    try:
                        # Анализ символа
                        analysis_result = await self.analyze_symbol(symbol)
                        if analysis_result:
                            # Отправка сигналов
                            await self.send_signals(symbol, analysis_result)

                    except Exception as e:
                        logger.error("Error processing {}: {}".format(
                            symbol, str(e)), exc_info=True)
                        continue

                # Логируем время выполнения цикла
                execution_time = (datetime.now() - start_time).total_seconds()
                logger.info(
                    "Analysis cycle completed in {:.2f} seconds".format(execution_time))

                # Ждем следующего цикла
                await asyncio.sleep(self.update_interval)

            except asyncio.CancelledError:
                logger.info("Signal analysis task cancelled")
                break
            except Exception as e:
                logger.error("Error in signal analysis loop: {}".format(
                    str(e)), exc_info=True)
                await asyncio.sleep(60)  # Ждем минуту перед повторной попыткой

    async def analyze_symbol(self, symbol: str) -> dict:
        """Анализ отдельного символа"""
        try:
            trader = TradingSystem(symbol)
            analysis = trader.analyze()

            if not analysis:
                logger.warning("No analysis results for {}".format(symbol))
                return None

            return analysis

        except Exception as e:
            logger.error("Error analyzing {}: {}".format(
                symbol, str(e)), exc_info=True)
            return None

    async def send_signals(self, symbol: str, analysis: dict):
        """Отправка сигналов подписчикам"""
        try:
            if analysis['signals'] or analysis['context']['suitable_for_trading']:
                message = format_signal_message(analysis)
                subscribers_count = len(self.subscribers)

                logger.info("Sending {} signal to {} subscribers".format(
                    symbol, subscribers_count))

                # Отправляем сообщения частями, чтобы не перегружать API
                batch_size = 25
                for i in range(0, subscribers_count, batch_size):
                    batch = list(self.subscribers)[i:i + batch_size]

                    for user_id in batch:
                        try:
                            await self.bot.send_message(user_id, message)
                            # Небольшая задержка между отправками
                            await asyncio.sleep(0.1)
                        except Exception as e:
                            error_msg = str(e).lower()
                            if "blocked" in error_msg or "chat not found" in error_msg:
                                logger.info(
                                    "Removing blocked user: {}".format(user_id))
                                self.subscribers.discard(user_id)
                            else:
                                logger.error("Error sending message to {}: {}".format(
                                    user_id, str(e)))

                    # Пауза между батчами
                    await asyncio.sleep(1)

                logger.info("Signals sent successfully for {}".format(symbol))
            else:
                logger.info("No significant signals for {}".format(symbol))

        except Exception as e:
            logger.error("Error sending signals for {}: {}".format(
                symbol, str(e)), exc_info=True)

    async def data_cleanup_loop(self):
        """Периодическая очистка старых данных"""
        while self.is_running:
            try:
                current_hour = datetime.now().hour

                # Запускаем очистку в начале каждого дня
                if current_hour == 0:
                    logger.info("Starting daily data cleanup")

                    for symbol in self.symbols:
                        try:
                            trader = TradingSystem(symbol)
                            # Храним данные за 30 дней
                            trader.cleanup_old_data(30)
                            logger.info(
                                "Cleaned up old data for {}".format(symbol))

                        except Exception as e:
                            logger.error("Error cleaning up data for {}: {}".format(
                                symbol, str(e)))

                    # Очищаем аналитику
                    try:
                        self.analytics_logger.cleanup_old_data(30)
                        logger.info("Analytics data cleanup completed")
                    except Exception as e:
                        logger.error(
                            "Error cleaning up analytics data: {}".format(str(e)))

                # Проверяем каждый час
                await asyncio.sleep(3600)

            except asyncio.CancelledError:
                logger.info("Data cleanup task cancelled")
                break
            except Exception as e:
                logger.error("Error in data cleanup loop: {}".format(
                    str(e)), exc_info=True)
                await asyncio.sleep(3600)

    async def get_status(self) -> dict:
        """Получение статуса фоновых задач"""
        status = {
            "is_running": self.is_running,
            "active_tasks": {
                name: {
                    "running": not task.done(),
                    "exception": task.exception() if task.done() else None
                }
                for name, task in self.tasks.items()
            },
            "subscribers_count": len(self.subscribers),
            "symbols": self.symbols,
            "update_interval": self.update_interval
        }
        return status


# Пример использования в main.py:
"""
from background_tasks import BackgroundTasks

# Инициализация
background_tasks = BackgroundTasks(bot, SYMBOLS, UPDATE_INTERVAL, subscribers)

# В функции startup
await background_tasks.start()

# В функции shutdown
await background_tasks.stop()

# Получение статуса
status = await background_tasks.get_status()
"""
