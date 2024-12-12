# bot.py

import asyncio
import logging
from datetime import datetime, timedelta
from string import Template

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import Config, load_config
from trading.signal_formatter import format_signal_message
from trading.trading_system import TradingSystem
from utils.analytics_logger import AnalyticsLogger


# Шаблоны сообщений
class MessageTemplates:
    START_MESSAGE = Template("""
👋 Привет! Я бот для отслеживания криптовалютных сигналов.

Доступные команды:
/start - Подписаться на сигналы
/stop - Отписаться от сигналов
/status - Текущий статус анализа
/symbols - Список отслеживаемых символов
/stats - Статистика сигналов
/analysis - Текущий анализ рынка
/settings - Настройки уведомлений""")

    STATUS_MESSAGE = Template("""
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

    STATS_HEADER = Template("""
📊 Статистика за $period:
Всего сигналов: $total_signals
Средняя сила сигналов: $avg_strength""")

    ANALYSIS_SIGNAL = Template("""- $type ($reason)
  Вход: $entry
  Стоп: $stop_loss
  Цель: $take_profit""")


# Настройка логирования
logger = logging.getLogger(__name__)

# Символы для мониторинга
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "DOTUSDT"]
UPDATE_INTERVAL = 180  # 3 минут

# Хранение подписчиков
subscribers = set()

# Инициализация бота
config = load_config()
bot = Bot(token=config.tg_bot.token)
dp = Dispatcher()


def get_statistics_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="24 часа", callback_data="stats_1")
    builder.button(text="7 дней", callback_data="stats_7")
    builder.button(text="30 дней", callback_data="stats_30")
    builder.adjust(3)
    return builder.as_markup()


@dp.message(Command("start"))
async def cmd_start(message: Message):
    subscribers.add(message.from_user.id)
    await message.answer(MessageTemplates.START_MESSAGE.substitute())


@dp.message(Command("stop"))
async def cmd_stop(message: Message):
    subscribers.discard(message.from_user.id)
    await message.answer("Вы отписались от уведомлений. Используйте /start чтобы подписаться снова.")


@dp.message(Command("status"))
async def cmd_status(message: Message):
    analytics = AnalyticsLogger()
    market_stats = analytics.get_market_statistics(1)

    status = MessageTemplates.STATUS_MESSAGE.substitute(
        subscribers=len(subscribers),
        symbols=", ".join(SYMBOLS),
        interval=UPDATE_INTERVAL,
        analyzed=market_stats['records_analyzed'],
        opportunities=market_stats['trading_opportunities'],
        trend_strength="{:.2f}".format(
            market_stats.get('avg_trend_strength', 0))
    )

    await message.answer(status)


@dp.message(Command("symbols"))
async def cmd_symbols(message: Message):
    analytics = AnalyticsLogger()
    symbols_message = ["📈 Отслеживаемые торговые пары:\n"]

    for symbol in SYMBOLS:
        trader = TradingSystem(symbol)
        analysis = trader.analyze()

        if analysis:
            trend = analysis['context']['trend']
            trend_emoji = "↗️" if trend == "uptrend" else "↘️" if trend == "downtrend" else "↔️"

            symbol_info = MessageTemplates.SYMBOL_INFO.substitute(
                trend_emoji=trend_emoji,
                symbol=symbol,
                price="{:.2f}".format(analysis['latest_price']),
                trend=trend,
                suitable="✅" if analysis['context']['suitable_for_trading'] else "❌"
            )
            symbols_message.append(symbol_info)

    await message.answer("".join(symbols_message))


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    await message.answer(
        "📊 Выберите период для статистики:",
        reply_markup=get_statistics_keyboard()
    )


@dp.callback_query(lambda c: c.data.startswith('stats_'))
async def process_stats_callback(callback_query: CallbackQuery):
    days = int(callback_query.data.split('_')[1])
    analytics = AnalyticsLogger()

    signal_stats = analytics.get_signal_statistics(days)
    market_stats = analytics.get_market_statistics(days)

    period_name = "24 часа" if days == 1 else "{} дней".format(days)

    stats_header = MessageTemplates.STATS_HEADER.substitute(
        period=period_name,
        total_signals=signal_stats['total_signals'],
        avg_strength="{:.2f}".format(signal_stats.get('avg_strength', 0))
    )

    stats_message = [stats_header, "\nРаспределение по типам:"]

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

    await callback_query.message.answer("\n".join(stats_message))
    await callback_query.answer()


@dp.message(Command("analysis"))
async def cmd_analysis(message: Message):
    analysis_message = ["📈 Текущий анализ рынка:\n"]

    for symbol in SYMBOLS:
        try:
            trader = TradingSystem(symbol)
            analysis = trader.analyze()

            if analysis:
                symbol_analysis = [
                    "\n{}:".format(symbol),
                    "Цена: {:.2f}".format(analysis['latest_price']),
                    "Тренд: {}".format(analysis['context']['trend']),
                    "Сила тренда: {:.2f}".format(
                        analysis['context']['strength']),
                    "RSI: {:.2f}".format(analysis.get('rsi', 0))
                ]

                if analysis['signals']:
                    symbol_analysis.append("\nАктивные сигналы:")
                    for signal in analysis['signals']:
                        signal_info = MessageTemplates.ANALYSIS_SIGNAL.substitute(
                            type=signal['type'].upper(),
                            reason=signal['reason'],
                            entry="{:.2f}".format(signal['entry']),
                            stop_loss="{:.2f}".format(signal['stop_loss']),
                            take_profit="{:.2f}".format(signal['take_profit'])
                        )
                        symbol_analysis.append(signal_info)
                else:
                    symbol_analysis.append("Нет активных сигналов")

                analysis_message.extend(symbol_analysis)

        except Exception as e:
            logger.error("Error analyzing {}: {}".format(symbol, e))
            analysis_message.append("\n{}: Ошибка анализа".format(symbol))

    # Разбиваем на части если сообщение слишком длинное
    max_length = 4096
    message_parts = []
    current_part = []
    current_length = 0

    for line in analysis_message:
        line_length = len(line) + 1
        if current_length + line_length > max_length:
            message_parts.append("\n".join(current_part))
            current_part = [line]
            current_length = line_length
        else:
            current_part.append(line)
            current_length += line_length

    if current_part:
        message_parts.append("\n".join(current_part))

    for part in message_parts:
        await message.answer(part)


async def send_signals():
    while True:
        try:
            logger.info("Starting signal analysis cycle")

            for symbol in SYMBOLS:
                try:
                    trader = TradingSystem(symbol)
                    analysis = trader.analyze()

                    if not analysis:
                        logger.warning(
                            "No analysis results for {}".format(symbol))
                        continue

                    message = format_signal_message(analysis)

                    if analysis['signals'] or analysis['context']['suitable_for_trading']:
                        logger.info("Sending signals for {} to {} subscribers".format(
                            symbol, len(subscribers)))
                        for user_id in subscribers:
                            try:
                                await bot.send_message(user_id, message)
                                await asyncio.sleep(0.1)
                            except Exception as e:
                                logger.error(
                                    "Error sending message to {}: {}".format(user_id, e))
                                if "blocked" in str(e).lower():
                                    subscribers.discard(user_id)
                    else:
                        logger.info(
                            "No significant signals for {}".format(symbol))

                except Exception as e:
                    logger.error("Error processing {}: {}".format(symbol, e))
                    continue

            if datetime.now().hour == 0:
                for symbol in SYMBOLS:
                    try:
                        trader = TradingSystem(symbol)
                        trader.cleanup_old_data(30)
                    except Exception as e:
                        logger.error(
                            "Error cleaning up data for {}: {}".format(symbol, e))

            logger.info(
                "Analysis cycle completed. Waiting {} seconds".format(UPDATE_INTERVAL))
            await asyncio.sleep(UPDATE_INTERVAL)

        except Exception as e:
            logger.error("Error in send_signals: {}".format(e))
            await asyncio.sleep(60)


async def main():
    logging.info("Starting bot")
    asyncio.create_task(send_signals())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
