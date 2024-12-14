import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Set

from aiogram import Bot

from config import TradingConfig
from trading.signal_formatter import format_signal_message
from trading.trading_system import TradingSystem
from utils.analytics_logger import AnalyticsLogger

logger = logging.getLogger(__name__)


class BackgroundTasks:
    def __init__(self, bot: Bot, config: TradingConfig, subscribers: Set[int]):
        """
        Инициализация фоновых задач
        Args:
            bot: Экземпляр бота
            config: Конфигурация торговли
            subscribers: Множество ID подписчиков
        """
        self.bot = bot
        self.config = config
        self.subscribers = subscribers
        self.tasks = {}
        self.is_running = False
        self.analytics_logger = AnalyticsLogger()

    async def start(self):
        """Запуск фоновых задач"""
        if not self.is_running:
            self.is_running = True
            self.tasks['signal_analysis'] = asyncio.create_task(
                self.signal_analysis_loop()
            )
            self.tasks['data_cleanup'] = asyncio.create_task(
                self.data_cleanup_loop()
            )
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
                logger.info(f"Task {task_name} stopped")
        self.tasks.clear()
        logger.info("All background tasks stopped")

    async def analyze_symbol(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Анализ отдельного символа
        Args:
            symbol: Символ для анализа
        Returns:
            Dict с результатами анализа или None в случае ошибки
        """
        try:
            trader = TradingSystem(symbol)
            analysis = trader.analyze()

            if not analysis:
                logger.warning(f"No analysis results for {symbol}")
                return None

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {str(e)}", exc_info=True)
            return None

    async def send_signals(self, symbol: str, analysis: Dict[str, Any]):
        """
        Отправка сигналов подписчикам
        Args:
            symbol: Символ
            analysis: Результаты анализа
        """
        try:
            if analysis['signals'] or analysis['context']['suitable_for_trading']:
                message = format_signal_message(analysis)
                subscribers_count = len(self.subscribers)

                logger.info(f"Sending {symbol} signal to {
                            subscribers_count} subscribers")

                # Отправляем сообщения батчами
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
                                    f"Removing blocked user: {user_id}")
                                self.subscribers.discard(user_id)
                            else:
                                logger.error(f"Error sending message to {
                                             user_id}: {str(e)}")

                    # Пауза между батчами
                    await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error sending signals for {
                         symbol}: {str(e)}", exc_info=True)

    async def signal_analysis_loop(self):
        """Основной цикл анализа сигналов"""
        while self.is_running:
            try:
                logger.info("Starting signal analysis cycle")
                start_time = datetime.now()

                for symbol in self.config.symbols:
                    try:
                        analysis_result = await self.analyze_symbol(symbol)
                        if analysis_result:
                            await self.send_signals(symbol, analysis_result)
                    except Exception as e:
                        logger.error(f"Error processing {symbol}: {
                                     str(e)}", exc_info=True)

                # Логируем время выполнения цикла
                execution_time = (datetime.now() - start_time).total_seconds()
                logger.info(f"Analysis cycle completed in {
                            execution_time:.2f} seconds")

                await asyncio.sleep(self.config.update_interval)

            except asyncio.CancelledError:
                logger.info("Signal analysis task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in signal analysis loop: {
                             str(e)}", exc_info=True)
                await asyncio.sleep(60)

    async def data_cleanup_loop(self):
        """Периодическая очистка старых данных"""
        while self.is_running:
            try:
                if datetime.now().hour == 0:  # Запускаем очистку в начале каждого дня
                    logger.info("Starting daily data cleanup")

                    for symbol in self.config.symbols:
                        try:
                            trader = TradingSystem(symbol)
                            # Храним данные за 30 дней
                            trader.cleanup_old_data(30)
                            logger.info(f"Cleaned up old data for {symbol}")
                        except Exception as e:
                            logger.error(f"Error cleaning up data for {
                                         symbol}: {str(e)}")

                    # Очищаем аналитику
                    try:
                        self.analytics_logger.cleanup_old_data(30)
                        logger.info("Analytics data cleanup completed")
                    except Exception as e:
                        logger.error(
                            f"Error cleaning up analytics data: {str(e)}")

                await asyncio.sleep(3600)  # Проверяем каждый час

            except asyncio.CancelledError:
                logger.info("Data cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in data cleanup loop: {
                             str(e)}", exc_info=True)
                await asyncio.sleep(3600)

    async def get_status(self) -> Dict[str, Any]:
        """
        Получение статуса фоновых задач
        Returns:
            Dict со статусом задач
        """
        return {
            "is_running": self.is_running,
            "active_tasks": {
                name: {
                    "running": not task.done(),
                    "exception": str(task.exception()) if task.done() and task.exception() else None
                }
                for name, task in self.tasks.items()
            },
            "subscribers_count": len(self.subscribers),
            "symbols": self.config.symbols,
            "update_interval": self.config.update_interval
        }
