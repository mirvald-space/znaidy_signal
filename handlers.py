import logging
from typing import Any, Dict, List, Set

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import TradingConfig
from trading.signal_formatter import format_signal_message
from trading.trading_system import TradingSystem
from utils.analytics_logger import AnalyticsLogger


class MessageTemplates:
    """Шаблоны сообщений для бота"""
    START = """
👋 Привет! Я бот для отслеживания криптовалютных сигналов.

Доступные команды:
/start - Подписаться на сигналы
/stop - Отписаться от сигналов
/status - Текущий статус анализа
/symbols - Список отслеживаемых символов
/stats - Статистика сигналов
/analysis - Текущий анализ рынка
/settings - Настройки уведомлений"""

    STATUS = """
📊 Текущий статус системы:
Активных подписчиков: {subscribers}
Отслеживаемые пары: {symbols}
Интервал обновления: {interval} секунд

Статистика за последние 24 часа:
Проанализировано: {analyzed} записей
Найдено возможностей: {opportunities}
Средняя сила тренда: {trend_strength:.2f}"""

    SYMBOL_STATUS = """{trend_emoji} {symbol}
   Цена: {price:.2f}
   Тренд: {trend}
   Подходит для торговли: {suitable}"""


class BotHandlers:
    def __init__(self, bot: Bot, config: TradingConfig):
        """
        Инициализация обработчиков команд
        Args:
            bot: Экземпляр бота
            config: Конфигурация торговли
        """
        self.bot = bot
        self.config = config
        self.router = Router()
        self.subscribers: Set[int] = set()
        self.analytics = AnalyticsLogger()
        self.setup_handlers()

    def get_statistics_keyboard(self) -> InlineKeyboardBuilder:
        """Создание клавиатуры для статистики"""
        builder = InlineKeyboardBuilder()
        builder.button(text="24 часа", callback_data="stats_1")
        builder.button(text="7 дней", callback_data="stats_7")
        builder.button(text="30 дней", callback_data="stats_30")
        builder.adjust(3)
        return builder.as_markup()

    def setup_handlers(self):
        """Настройка обработчиков команд"""

        @self.router.message(Command("start"))
        async def cmd_start(message: Message):
            self.subscribers.add(message.from_user.id)
            await message.answer(MessageTemplates.START)

        @self.router.message(Command("stop"))
        async def cmd_stop(message: Message):
            self.subscribers.discard(message.from_user.id)
            await message.answer(
                "Вы отписались от уведомлений. Используйте /start чтобы подписаться снова."
            )

        @self.router.message(Command("status"))
        async def cmd_status(message: Message):
            market_stats = self.analytics.get_market_statistics(1)

            status = MessageTemplates.STATUS.format(
                subscribers=len(self.subscribers),
                symbols=", ".join(self.config.symbols),
                interval=self.config.update_interval,
                analyzed=market_stats['records_analyzed'],
                opportunities=market_stats['trading_opportunities'],
                trend_strength=market_stats.get('avg_trend_strength', 0)
            )

            await message.answer(status)

        @self.router.message(Command("symbols"))
        async def cmd_symbols(message: Message):
            symbols_message = ["📈 Отслеживаемые торговые пары:\n"]

            for symbol in self.config.symbols:
                try:
                    trader = TradingSystem(symbol)
                    analysis = trader.analyze()

                    if analysis:
                        trend = analysis['context']['trend']
                        trend_emoji = self.get_trend_emoji(trend)

                        symbol_info = MessageTemplates.SYMBOL_STATUS.format(
                            trend_emoji=trend_emoji,
                            symbol=symbol,
                            price=analysis['latest_price'],
                            trend=trend,
                            suitable="✅" if analysis['context']['suitable_for_trading'] else "❌"
                        )
                        symbols_message.append(symbol_info)
                except Exception as e:
                    symbols_message.append(
                        f"{symbol} - Ошибка анализа: {str(e)}\n")

            await message.answer("\n".join(symbols_message))

        @self.router.message(Command("stats"))
        async def cmd_stats(message: Message):
            await message.answer(
                "📊 Выберите период для статистики:",
                reply_markup=self.get_statistics_keyboard()
            )

        @self.router.callback_query(F.data.startswith('stats_'))
        async def process_stats_callback(callback: CallbackQuery):
            days = int(callback.data.split('_')[1])

            signal_stats = self.analytics.get_signal_statistics(days)
            market_stats = self.analytics.get_market_statistics(days)

            period_name = "24 часа" if days == 1 else f"{days} дней"

            stats_message = self.format_stats_message(
                period_name, signal_stats, market_stats
            )

            await callback.message.answer("\n".join(stats_message))
            await callback.answer()

        @self.router.message(Command("analysis"))
        async def cmd_analysis(message: Message):
            analysis_messages = await self.perform_market_analysis()

            # Отправляем сообщения частями из-за ограничений Telegram
            for msg in analysis_messages:
                await message.answer(msg)

        @self.router.message(Command("settings"))
        async def cmd_settings(message: Message):
            settings = (
                "⚙️ Настройки уведомлений:\n"
                f"🔄 Интервал обновления: {
                    self.config.update_interval} секунд\n"
                f"📊 Отслеживаемые пары: {', '.join(self.config.symbols)}\n"
                f"📈 Таймфрейм: {self.config.timeframe}\n"
                "\nДля изменения настроек обратитесь к администратору"
            )
            await message.answer(settings)

    @staticmethod
    def get_trend_emoji(trend: str) -> str:
        """Получение эмодзи для тренда"""
        return {
            "uptrend": "↗️",
            "downtrend": "↘️"
        }.get(trend, "↔️")

    def format_stats_message(self, period: str, signal_stats: Dict, market_stats: Dict) -> List[str]:
        """Форматирование сообщения со статистикой"""
        stats_message = [
            f"📊 Статистика за {period}:\n",
            f"Всего сигналов: {signal_stats['total_signals']}",
            f"Средняя сила сигналов: {
                signal_stats.get('avg_strength', 0):.2f}",
            "\nРаспределение по типам:"
        ]

        # Добавляем статистику по типам сигналов
        for type_, count in signal_stats.get('by_type', {}).items():
            stats_message.append(f"- {type_}: {count}")

        # Добавляем рыночную статистику
        stats_message.extend([
            "\nРыночная статистика:",
            f"Проанализировано: {market_stats['records_analyzed']} записей",
            f"Торговых возможностей: {market_stats['trading_opportunities']}",
            f"Средняя сила тренда: {market_stats.get(
                'avg_trend_strength', 0):.2f}",
            "\nРаспределение трендов:"
        ])

        # Добавляем распределение трендов
        for trend, count in market_stats.get('trend_distribution', {}).items():
            stats_message.append(f"- {trend}: {count}")

        return stats_message

    async def perform_market_analysis(self) -> List[str]:
        """Выполнение анализа рынка"""
        analysis_message = ["📈 Текущий анализ рынка:\n"]
        current_message_length = 0
        messages = []

        for symbol in self.config.symbols:
            try:
                trader = TradingSystem(symbol)
                analysis = trader.analyze()

                if analysis:
                    # Форматируем сообщение для текущего символа
                    symbol_analysis = format_signal_message(analysis)

                    # Проверяем, не превысит ли добавление нового анализа лимит
                    if current_message_length + len(symbol_analysis) > 4000:
                        messages.append("\n".join(analysis_message))
                        analysis_message = []
                        current_message_length = 0

                    analysis_message.append(symbol_analysis)
                    current_message_length += len(symbol_analysis)

            except Exception as e:
                analysis_message.append(
                    f"\n{symbol}: Ошибка анализа: {str(e)}")

        if analysis_message:
            messages.append("\n".join(analysis_message))

        return messages

    def get_router(self) -> Router:
        """Получение роутера для регистрации в диспетчере"""
        return self.router

    def get_subscribers(self) -> Set[int]:
        """Получение множества подписчиков"""
        return self.subscribers
