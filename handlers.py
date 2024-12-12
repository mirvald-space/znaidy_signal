# handlers.py
import logging
from datetime import datetime
from string import Template
from typing import Any, Dict

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, Update
from aiogram.utils.keyboard import InlineKeyboardBuilder

from trading.trading_system import TradingSystem
from utils.analytics_logger import AnalyticsLogger

logger = logging.getLogger(__name__)


class BotHandlers:
    def __init__(self, bot: Bot, symbols: list, update_interval: int):
        self.bot = bot
        self.router = Router()
        self.subscribers = set()
        self.symbols = symbols
        self.update_interval = update_interval
        self.setup_handlers()

    class MessageTemplates:
        START = Template("""
👋 Привет! Я бот для отслеживания криптовалютных сигналов.

Доступные команды:
/start - Подписаться на сигналы
/stop - Отписаться от сигналов
/status - Текущий статус анализа
/symbols - Список отслеживаемых символов
/stats - Статистика сигналов
/analysis - Текущий анализ рынка
/settings - Настройки уведомлений""")

        STATUS = Template("""
📊 Текущий статус системы:
Активных подписчиков: $subscribers
Отслеживаемые пары: $symbols
Интервал обновления: $interval секунд

Статистика за последние 24 часа:
Проанализировано: $analyzed записей
Найдено возможностей: $opportunities
Средняя сила тренда: $trend_strength""")

        SYMBOL_INFO = Template("""$trend_emoji $symbol
   Цена: $price
   Тренд: $trend
   Подходит для торговли: $suitable
""")

        ANALYSIS_HEADER = Template("""
📈 Анализ $symbol:
Цена: $price
Тренд: $trend
Сила тренда: $strength
RSI: $rsi""")

        SIGNAL = Template("""
- $type ($reason)
  Вход: $entry
  Стоп: $stop_loss
  Цель: $take_profit""")

    def get_statistics_keyboard(self):
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
            await message.answer(self.MessageTemplates.START.substitute())

        @self.router.message(Command("stop"))
        async def cmd_stop(message: Message):
            self.subscribers.discard(message.from_user.id)
            await message.answer(
                "Вы отписались от уведомлений. Используйте /start чтобы подписаться снова."
            )

        @self.router.message(Command("status"))
        async def cmd_status(message: Message):
            analytics = AnalyticsLogger()
            market_stats = analytics.get_market_statistics(1)

            status = self.MessageTemplates.STATUS.substitute(
                subscribers=len(self.subscribers),
                symbols=", ".join(self.symbols),
                interval=self.update_interval,
                analyzed=market_stats['records_analyzed'],
                opportunities=market_stats['trading_opportunities'],
                trend_strength="{:.2f}".format(
                    market_stats.get('avg_trend_strength', 0))
            )

            await message.answer(status)

        @self.router.message(Command("symbols"))
        async def cmd_symbols(message: Message):
            analytics = AnalyticsLogger()
            symbols_message = ["📈 Отслеживаемые торговые пары:\n"]

            for symbol in self.symbols:
                try:
                    trader = TradingSystem(symbol)
                    analysis = trader.analyze()

                    if analysis:
                        trend = analysis['context']['trend']
                        trend_emoji = "↗️" if trend == "uptrend" else "↘️" if trend == "downtrend" else "↔️"

                        symbol_info = self.MessageTemplates.SYMBOL_INFO.substitute(
                            trend_emoji=trend_emoji,
                            symbol=symbol,
                            price="{:.2f}".format(analysis['latest_price']),
                            trend=trend,
                            suitable="✅" if analysis['context']['suitable_for_trading'] else "❌"
                        )
                        symbols_message.append(symbol_info)
                except Exception as e:
                    symbols_message.append(
                        "{} - Ошибка анализа\n".format(symbol))

            await message.answer("".join(symbols_message))

        @self.router.message(Command("stats"))
        async def cmd_stats(message: Message):
            await message.answer(
                "📊 Выберите период для статистики:",
                reply_markup=self.get_statistics_keyboard()
            )

        @self.router.callback_query(F.data.startswith('stats_'))
        async def process_stats_callback(callback: CallbackQuery):
            days = int(callback.data.split('_')[1])
            analytics = AnalyticsLogger()

            signal_stats = analytics.get_signal_statistics(days)
            market_stats = analytics.get_market_statistics(days)

            period_name = "24 часа" if days == 1 else "{} дней".format(days)

            stats_message = [
                "📊 Статистика за {}:\n".format(period_name),
                "Всего сигналов: {}".format(signal_stats['total_signals']),
                "Средняя сила сигналов: {:.2f}".format(
                    signal_stats.get('avg_strength', 0)),
                "\nРаспределение по типам:"
            ]

            for type_, count in signal_stats.get('by_type', {}).items():
                stats_message.append("- {}: {}".format(type_, count))

            stats_message.extend([
                "\nРыночная статистика:",
                "Проанализировано: {} записей".format(
                    market_stats['records_analyzed']),
                "Торговых возможностей: {}".format(
                    market_stats['trading_opportunities']),
                "Средняя сила тренда: {:.2f}".format(
                    market_stats.get('avg_trend_strength', 0)),
                "\nРаспределение трендов:"
            ])

            for trend, count in market_stats.get('trend_distribution', {}).items():
                stats_message.append("- {}: {}".format(trend, count))

            await callback.message.answer("\n".join(stats_message))
            await callback.answer()

        @self.router.message(Command("analysis"))
        async def cmd_analysis(message: Message):
            analysis_message = ["📈 Текущий анализ рынка:\n"]

            for symbol in self.symbols:
                try:
                    trader = TradingSystem(symbol)
                    analysis = trader.analyze()

                    if analysis:
                        header = self.MessageTemplates.ANALYSIS_HEADER.substitute(
                            symbol=symbol,
                            price="{:.2f}".format(analysis['latest_price']),
                            trend=analysis['context']['trend'],
                            strength="{:.2f}".format(
                                analysis['context']['strength']),
                            rsi="{:.2f}".format(analysis.get('rsi', 0))
                        )
                        analysis_message.append(header)

                        if analysis['signals']:
                            analysis_message.append("\nАктивные сигналы:")
                            for signal in analysis['signals']:
                                signal_info = self.MessageTemplates.SIGNAL.substitute(
                                    type=signal['type'].upper(),
                                    reason=signal['reason'],
                                    entry="{:.2f}".format(signal['entry']),
                                    stop_loss="{:.2f}".format(
                                        signal['stop_loss']),
                                    take_profit="{:.2f}".format(
                                        signal['take_profit'])
                                )
                                analysis_message.append(signal_info)
                        else:
                            analysis_message.append("\nНет активных сигналов")
                        analysis_message.append("\n")

                except Exception as e:
                    analysis_message.append(
                        "\n{}: Ошибка анализа\n".format(symbol))

            # Разбиваем на части если сообщение слишком длинное
            await self.send_long_message(message, analysis_message)

        @self.router.message(Command("settings"))
        async def cmd_settings(message: Message):
            await message.answer(
                "⚙️ Настройки уведомлений:\n"
                "🔄 Интервал обновления: {} секунд\n"
                "📊 Отслеживаемые пары: {}\n"
                "\nДля изменения настроек обратитесь к администратору".format(
                    self.update_interval,
                    ", ".join(self.symbols)
                )
            )

        @self.router.errors()
        async def handle_errors(update: Update, exception: Exception):
            """Обработчик ошибок"""
            error_message = "Произошла ошибка при обработке запроса: {}".format(
                str(exception))
            if update.message:
                await update.message.answer(error_message)
            logger.error(error_message, exc_info=True)

    async def send_long_message(self, message: Message, lines: list):
        """Отправка длинного сообщения по частям"""
        max_length = 4096
        parts = []
        current_part = []
        current_length = 0

        for line in lines:
            line_length = len(line) + 1
            if current_length + line_length > max_length:
                parts.append("\n".join(current_part))
                current_part = [line]
                current_length = line_length
            else:
                current_part.append(line)
                current_length += line_length

        if current_part:
            parts.append("\n".join(current_part))

        for part in parts:
            await message.answer(part)

    def get_router(self):
        """Получение роутера для регистрации в диспетчере"""
        return self.router

    def get_subscribers(self):
        """Получение списка подписчиков"""
        return self.subscribers


# Пример использования в main.py:
"""
from aiogram import Bot, Dispatcher
from handlers import BotHandlers

# Инициализация
bot = Bot(token=TOKEN)
handlers = BotHandlers(bot, SYMBOLS, UPDATE_INTERVAL)
dp = Dispatcher()
dp.include_router(handlers.get_router())

# Доступ к подписчикам
subscribers = handlers.get_subscribers()
"""
