import asyncio
import logging
from datetime import datetime
from string import Template
from typing import Any, Dict, List, Optional, Set

from aiogram import Bot

from config import TradingConfig
from trading.signal_formatter import (
    add_market_context,
    format_pre_signal_message,
    format_signal_message,
)
from trading.trading_system import TradingSystem
from utils.analytics_logger import AnalyticsLogger

logger = logging.getLogger(__name__)


class LogTemplates:
    TASK_STOPPED = Template("Task $task_name stopped")
    BLOCKED_USER = Template("Removing blocked user: $user_id")
    SEND_ERROR = Template("Error sending message to $user_id: $error")
    SIGNALS_COUNT = Template("Sending $count $signal_type for $symbol")
    SYMBOL_PROCESS = Template("Processing symbol: $symbol")
    NO_ANALYSIS = Template("No analysis results for $symbol")
    SYMBOL_ERROR = Template("Error processing $symbol: $error")
    CYCLE_TIME = Template("Analysis cycle completed in $time seconds")
    ANALYSIS_ERROR = Template("Error in signal analysis loop: $error")
    CLEANUP_SYMBOL = Template("Cleaned up old data for $symbol")
    CLEANUP_ERROR = Template("Error cleaning up data for $symbol: $error")
    ANALYTICS_ERROR = Template("Error cleaning up analytics data: $error")
    STATUS_ERROR = Template("Error getting status: $error")


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
        self.signal_cache = {}

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
                logger.info(LogTemplates.TASK_STOPPED.substitute(
                    task_name=task_name))
        self.tasks.clear()
        logger.info("All background tasks stopped")

    def is_signal_duplicate(self, symbol: str, signal_type: str, entry: float, timestamp: datetime) -> bool:
        """
        Проверка на дубликат сигнала
        Args:
            symbol: Торговый символ
            signal_type: Тип сигнала
            entry: Цена входа
            timestamp: Время сигнала
        Returns:
            bool: True если сигнал дубликат
        """
        cache_key = "_".join([symbol, signal_type])
        if cache_key in self.signal_cache:
            last_signal = self.signal_cache[cache_key]
            time_diff = (timestamp - last_signal['timestamp']).total_seconds()
            price_diff = abs(
                entry - last_signal['entry']) / last_signal['entry']

            if time_diff < 1800 and price_diff < 0.005:
                return True

        self.signal_cache[cache_key] = {
            'timestamp': timestamp,
            'entry': entry
        }
        return False

    async def send_messages(self, messages: List[str], priority: bool = False):
        """
        Отправка сообщений подписчикам с учетом приоритета
        Args:
            messages: Список сообщений для отправки
            priority: Приоритетность сообщений
        """
        subscribers_count = len(self.subscribers)
        batch_size = 25 if priority else 15
        delay = 0.1 if priority else 0.3

        for i in range(0, subscribers_count, batch_size):
            batch = list(self.subscribers)[i:i + batch_size]

            for user_id in batch:
                try:
                    for message in messages:
                        await self.bot.send_message(user_id, message)
                        await asyncio.sleep(delay)
                except Exception as e:
                    error_msg = str(e).lower()
                    if "blocked" in error_msg or "chat not found" in error_msg:
                        logger.info(
                            LogTemplates.BLOCKED_USER.substitute(user_id=user_id))
                        self.subscribers.discard(user_id)
                    else:
                        logger.error(LogTemplates.SEND_ERROR.substitute(
                            user_id=user_id,
                            error=str(e)
                        ))

            await asyncio.sleep(1)

    async def process_signals(self, symbol: str, analysis: Dict[str, Any]):
        """
        Обработка сигналов и отправка уведомлений
        Args:
            symbol: Торговый символ
            analysis: Результаты анализа
        """
        try:
            timestamp = datetime.now()
            messages = []

            for pre_signal in analysis.get('pre_signals', []):
                if pre_signal['probability'] >= 0.6:
                    if not self.is_signal_duplicate(symbol, pre_signal['type'], pre_signal['current_price'], timestamp):
                        message = format_pre_signal_message(
                            symbol, pre_signal, timestamp)
                        message = add_market_context(
                            message, analysis['context'])
                        messages.append(message)

            if messages:
                logger.info(LogTemplates.SIGNALS_COUNT.substitute(
                    count=len(messages),
                    signal_type='pre-signals',
                    symbol=symbol
                ))
                await self.send_messages(messages)

            signal_messages = []
            for signal in analysis.get('signals', []):
                if signal['strength'] >= 0.7:
                    if not self.is_signal_duplicate(symbol, signal['type'], signal['entry'], timestamp):
                        message = format_signal_message(
                            symbol, signal, timestamp)
                        message = add_market_context(
                            message, analysis['context'])
                        signal_messages.append(message)

            if signal_messages:
                logger.info(LogTemplates.SIGNALS_COUNT.substitute(
                    count=len(signal_messages),
                    signal_type='signals',
                    symbol=symbol
                ))
                await self.send_messages(signal_messages, priority=True)

        except Exception as e:
            logger.error(LogTemplates.SYMBOL_ERROR.substitute(
                symbol=symbol,
                error=str(e)
            ), exc_info=True)

    async def signal_analysis_loop(self):
        """Основной цикл анализа сигналов"""
        while self.is_running:
            try:
                logger.info("Starting signal analysis cycle")
                start_time = datetime.now()

                for symbol in self.config.symbols:
                    try:
                        clean_symbol = str(symbol).strip('[]"\' ').upper()
                        logger.info(LogTemplates.SYMBOL_PROCESS.substitute(
                            symbol=clean_symbol))

                        trader = TradingSystem(clean_symbol)
                        analysis = trader.analyze()

                        if analysis:
                            await self.process_signals(clean_symbol, analysis)
                        else:
                            logger.warning(
                                LogTemplates.NO_ANALYSIS.substitute(symbol=clean_symbol))

                    except Exception as e:
                        logger.error(LogTemplates.SYMBOL_ERROR.substitute(
                            symbol=symbol,
                            error=str(e)
                        ), exc_info=True)

                execution_time = (datetime.now() - start_time).total_seconds()
                logger.info(LogTemplates.CYCLE_TIME.substitute(
                    time=f"{execution_time:.2f}"))
                await asyncio.sleep(self.config.update_interval)

            except asyncio.CancelledError:
                logger.info("Signal analysis task cancelled")
                break
            except Exception as e:
                logger.error(LogTemplates.ANALYSIS_ERROR.substitute(
                    error=str(e)), exc_info=True)
                await asyncio.sleep(60)

    async def data_cleanup_loop(self):
        """Периодическая очистка старых данных"""
        while self.is_running:
            try:
                current_hour = datetime.now().hour

                if current_hour == 0:
                    logger.info("Starting daily data cleanup")

                    for symbol in self.config.symbols:
                        try:
                            clean_symbol = str(symbol).strip('[]"\' ').upper()
                            trader = TradingSystem(clean_symbol)
                            trader.cleanup_old_data(30)
                            logger.info(LogTemplates.CLEANUP_SYMBOL.substitute(
                                symbol=clean_symbol))
                        except Exception as e:
                            logger.error(LogTemplates.CLEANUP_ERROR.substitute(
                                symbol=symbol,
                                error=str(e)
                            ))

                    try:
                        self.analytics_logger.cleanup_old_data(30)
                        logger.info("Analytics data cleanup completed")
                    except Exception as e:
                        logger.error(
                            LogTemplates.ANALYTICS_ERROR.substitute(error=str(e)))

                    self.signal_cache.clear()
                    logger.info("Signal cache cleared")

                await asyncio.sleep(3600)

            except asyncio.CancelledError:
                logger.info("Data cleanup task cancelled")
                break
            except Exception as e:
                logger.error(LogTemplates.ANALYSIS_ERROR.substitute(
                    error=str(e)), exc_info=True)
                await asyncio.sleep(3600)

    async def get_status(self) -> Dict[str, Any]:
        """
        Получение статуса фоновых задач
        Returns:
            Dict со статусом задач
        """
        try:
            signal_stats = self.analytics_logger.get_signal_statistics(1)

            return {
                "is_running": self.is_running,
                "active_tasks": {
                    name: {
                        "running": not task.done(),
                        "exception": str(task.exception()) if task.done() and task.exception() else None
                    }
                    for name, task in self.tasks.items()
                },
                "trading": {
                    "symbols": self.config.symbols,
                    "update_interval": self.config.update_interval,
                    "signals_24h": signal_stats.get('total_signals', 0),
                    "avg_strength": signal_stats.get('avg_strength', 0)
                },
                "subscribers_count": len(self.subscribers),
                "last_update": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(LogTemplates.STATUS_ERROR.substitute(
                error=str(e)), exc_info=True)
            return {
                "error": str(e),
                "is_running": self.is_running,
                "last_update": datetime.now().isoformat()
            }
