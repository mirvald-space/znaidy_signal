# bot.py

import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import Config, load_config
from trading.signal_formatter import format_signal_message
from trading.trading_system import TradingSystem
from utils.analytics_logger import AnalyticsLogger

# Настройка логирования
logger = logging.getLogger(__name__)

# Символы для мониторинга
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
UPDATE_INTERVAL = 300  # 5 минут

# Хранение подписчиков (в реальном приложении лучше использовать базу данных)
subscribers = set()

# Инициализация бота
config = load_config()
bot = Bot(token=config.tg_bot.token)
dp = Dispatcher()


def get_statistics_keyboard():
    """Создание клавиатуры для статистики"""
    builder = InlineKeyboardBuilder()
    builder.button(text="24 часа", callback_data="stats_1")
    builder.button(text="7 дней", callback_data="stats_7")
    builder.button(text="30 дней", callback_data="stats_30")
    builder.adjust(3)
    return builder.as_markup()


@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    subscribers.add(message.from_user.id)
    await message.answer(
        "👋 Привет! Я бот для отслеживания криптовалютных сигналов.\n\n"
        "Доступные команды:\n"
        "/start - Подписаться на сигналы\n"
        "/stop - Отписаться от сигналов\n"
        "/status - Текущий статус анализа\n"
        "/symbols - Список отслеживаемых символов\n"
        "/stats - Статистика сигналов\n"
        "/analysis - Текущий анализ рынка\n"
        "/settings - Настройки уведомлений"
    )


@dp.message(Command("stop"))
async def cmd_stop(message: Message):
    """Обработчик команды /stop"""
    subscribers.discard(message.from_user.id)
    await message.answer("Вы отписались от уведомлений. Используйте /start чтобы подписаться снова.")


@dp.message(Command("status"))
async def cmd_status(message: Message):
    """Обработчик команды /status"""
    analytics = AnalyticsLogger()
    status_message = [
        "📊 Текущий статус системы:",
        f"Активных подписчиков: {len(subscribers)}",
        f"Отслеживаемые пары: {', '.join(SYMBOLS)}",
        f"Интервал обновления: {UPDATE_INTERVAL} секунд",
        "",
        "Статистика за последние 24 часа:",
    ]

    # Получаем статистику за последние 24 часа
    market_stats = analytics.get_market_statistics(1)
    status_message.extend([
        f"Проанализировано: {market_stats['records_analyzed']} записей",
        f"Найдено возможностей: {market_stats['trading_opportunities']}",
        f"Средняя сила тренда: {market_stats.get('avg_trend_strength', 0):.2f}"
    ])

    await message.answer("\n".join(status_message))


@dp.message(Command("symbols"))
async def cmd_symbols(message: Message):
    """Обработчик команды /symbols"""
    analytics = AnalyticsLogger()
    market_stats = analytics.get_market_statistics(1)  # За последние 24 часа

    symbols_message = ["📈 Отслеживаемые торговые пары:\n"]

    for symbol in SYMBOLS:
        # Получаем статистику по символу
        trader = TradingSystem(symbol)
        analysis = trader.analyze()

        if analysis:
            trend = analysis['context']['trend']
            trend_emoji = "↗️" if trend == "uptrend" else "↘️" if trend == "downtrend" else "↔️"
            suitable = "✅" if analysis['context']['suitable_for_trading'] else "❌"

            symbols_message.append(
                f"{trend_emoji} {symbol}\n"
                f"   Цена: {analysis['latest_price']:.2f}\n"
                f"   Тренд: {trend}\n"
                f"   Подходит для торговли: {suitable}\n"
            )

    await message.answer("".join(symbols_message))


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    """Обработчик команды /stats"""
    await message.answer(
        "📊 Выберите период для статистики:",
        reply_markup=get_statistics_keyboard()
    )


@dp.callback_query(lambda c: c.data.startswith('stats_'))
async def process_stats_callback(callback_query: CallbackQuery):
    """Обработчик нажатий кнопок статистики"""
    days = int(callback_query.data.split('_')[1])
    analytics = AnalyticsLogger()

    signal_stats = analytics.get_signal_statistics(days)
    market_stats = analytics.get_market_statistics(days)

    period_name = "24 часа" if days == 1 else f"{days} дней"

    stats_message = [
        f"📊 Статистика за {period_name}:\n",
        f"Всего сигналов: {signal_stats['total_signals']}",
        f"Средняя сила сигналов: {signal_stats.get('avg_strength', 0):.2f}",
        "\nРаспределение по типам:"
    ]

    for type_, count in signal_stats.get('by_type', {}).items():
        stats_message.append(f"- {type_}: {count}")

    stats_message.extend([
        "\nРыночная статистика:",
        f"Проанализировано: {market_stats['records_analyzed']} записей",
        f"Торговых возможностей: {market_stats['trading_opportunities']}",
        f"Средняя сила тренда: {market_stats.get(
            'avg_trend_strength', 0):.2f}",
        "\nРаспределение трендов:"
    ])

    for trend, count in market_stats.get('trend_distribution', {}).items():
        stats_message.append(f"- {trend}: {count}")

    await callback_query.message.answer("\n".join(stats_message))
    await callback_query.answer()


@dp.message(Command("analysis"))
async def cmd_analysis(message: Message):
    """Обработчик команды /analysis - текущий анализ всех пар"""
    analysis_message = ["📈 Текущий анализ рынка:\n"]

    for symbol in SYMBOLS:
        try:
            trader = TradingSystem(symbol)
            analysis = trader.analyze()

            if analysis:
                analysis_message.append(f"\n{symbol}:")
                analysis_message.append(
                    f"Цена: {analysis['latest_price']:.2f}")
                analysis_message.append(
                    f"Тренд: {analysis['context']['trend']}")
                analysis_message.append(
                    f"Сила тренда: {analysis['context']['strength']:.2f}")
                analysis_message.append(f"RSI: {analysis.get('rsi', 0):.2f}")

                if analysis['signals']:
                    analysis_message.append("\nАктивные сигналы:")
                    for signal in analysis['signals']:
                        analysis_message.extend([
                            f"- {signal['type'].upper()} ({signal['reason']})",
                            f"  Вход: {signal['entry']:.2f}",
                            f"  Стоп: {signal['stop_loss']:.2f}",
                            f"  Цель: {signal['take_profit']:.2f}"
                        ])
                else:
                    analysis_message.append("Нет активных сигналов")

        except Exception as e:
            logger.error(f"Error analyzing {symbol}: {e}")
            analysis_message.append(f"\n{symbol}: Ошибка анализа")

    # Разбиваем на части если сообщение слишком длинное
    max_length = 4096
    message_parts = []
    current_part = []
    current_length = 0

    for line in analysis_message:
        line_length = len(line) + 1  # +1 для \n
        if current_length + line_length > max_length:
            message_parts.append("\n".join(current_part))
            current_part = [line]
            current_length = line_length
        else:
            current_part.append(line)
            current_length += line_length

    if current_part:
        message_parts.append("\n".join(current_part))

    # Отправляем части сообщения
    for part in message_parts:
        await message.answer(part)


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
                        logger.info(f"Sending signals for {symbol} to {
                                    len(subscribers)} subscribers")
                        for user_id in subscribers:
                            try:
                                await bot.send_message(user_id, message)
                                # Небольшая задержка между отправками
                                await asyncio.sleep(0.1)
                            except Exception as e:
                                logger.error(f"Error sending message to {
                                             user_id}: {e}")
                                if "blocked" in str(e).lower():
                                    subscribers.discard(user_id)
                    else:
                        logger.info(f"No significant signals for {symbol}")

                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")
                    continue

            # Очистка старых данных раз в день
            if datetime.now().hour == 0:
                for symbol in SYMBOLS:
                    try:
                        trader = TradingSystem(symbol)
                        trader.cleanup_old_data(30)  # Храним данные за 30 дней
                    except Exception as e:
                        logger.error(
                            f"Error cleaning up data for {symbol}: {e}")

            logger.info(f"Analysis cycle completed. Waiting {
                        UPDATE_INTERVAL} seconds")
            await asyncio.sleep(UPDATE_INTERVAL)

        except Exception as e:
            logger.error(f"Error in send_signals: {e}")
            await asyncio.sleep(60)  # Ждем минуту перед повторной попыткой


async def main():
    logging.info("Starting bot")
    # Запускаем отправку сигналов в фоновом режиме
    asyncio.create_task(send_signals())
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
