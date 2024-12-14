from datetime import datetime
from typing import Any, Dict


class SignalTemplates:
    PRE_SIGNAL = """⚠️ ПОДГОТОВКА К СИГНАЛУ: {symbol}

💰 Текущая цена: {price:.2f}
📈 Тип: {signal_type}
ℹ️ Причина: {reason}
⚡️ Вероятность сигнала: {probability:.0%}
⏰ Время: {timestamp}

💡 Рекомендация: {recommendation}
"""

    SIGNAL = """🚨 ТОРГОВЫЙ СИГНАЛ: {symbol}

💰 Текущая цена: {price:.2f}
📈 Тип сделки: {signal_type}
ℹ️ Причина: {reason}

📍 Точка входа: {entry:.2f}
🛑 Стоп-лосс: {stop_loss:.2f} ({sl_percent:.1f}%)
✅ Тейк-профит: {take_profit:.2f} ({tp_percent:.1f}%)
💪 Сила сигнала: {strength:.0%}

⏰ Время сигнала: {timestamp}
"""

    MARKET_CONTEXT = """
📊 Рыночный контекст:
• Тренд: {trend}
• Объем: {volume}
• Волатильность: {volatility}
"""


def get_signal_type_emoji(signal_type: str) -> str:
    """Получение эмодзи для типа сигнала"""
    if "long" in signal_type.lower():
        return "📈 ПОКУПКА"
    elif "short" in signal_type.lower():
        return "📉 ПРОДАЖА"
    return "📊 НЕОПРЕДЕЛЕНО"


def get_recommendation(pre_signal: Dict[str, Any]) -> str:
    """Формирование рекомендации на основе предварительного сигнала"""
    signal_type = "long" in pre_signal['type'].lower()
    probability = pre_signal['probability']

    if probability > 0.8:
        base_text = "Высокая вероятность сигнала на {}. Подготовьте ордер."
    elif probability > 0.6:
        base_text = "Средняя вероятность сигнала на {}. Следите за развитием ситуации."
    else:
        base_text = "Возможен сигнал на {}. Ждите подтверждения."

    action = "покупку" if signal_type else "продажу"
    return base_text.format(action)


def format_pre_signal_message(symbol: str, pre_signal: Dict[str, Any], timestamp: datetime) -> str:
    """Форматирование предварительного сигнала"""
    return SignalTemplates.PRE_SIGNAL.format(
        symbol=symbol,
        price=pre_signal['current_price'],
        signal_type=get_signal_type_emoji(pre_signal['type']),
        reason=pre_signal['reason'],
        probability=pre_signal['probability'],
        timestamp=timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        recommendation=get_recommendation(pre_signal)
    )


def format_signal_message(symbol: str, signal: Dict[str, Any], timestamp: datetime) -> str:
    """Форматирование торгового сигнала"""
    entry_price = signal['entry']
    sl_price = signal['stop_loss']
    tp_price = signal['take_profit']

    # Расчет процентов для стоп-лосса и тейк-профита
    sl_percent = abs((sl_price - entry_price) / entry_price * 100)
    tp_percent = abs((tp_price - entry_price) / entry_price * 100)

    return SignalTemplates.SIGNAL.format(
        symbol=symbol,
        price=entry_price,
        signal_type=get_signal_type_emoji(signal['type']),
        reason=signal['reason'],
        entry=entry_price,
        stop_loss=sl_price,
        take_profit=tp_price,
        sl_percent=sl_percent,
        tp_percent=tp_percent,
        strength=signal['strength'],
        timestamp=timestamp.strftime('%Y-%m-%d %H:%M:%S')
    )


def add_market_context(message: str, context: Dict[str, Any]) -> str:
    """Добавление рыночного контекста к сообщению"""
    trend_emoji = {
        "uptrend": "🟢 Восходящий",
        "downtrend": "🔴 Нисходящий",
        "undefined": "⚪️ Неопределенный"
    }.get(context['trend'], "⚪️ Неопределенный")

    volume_emoji = {
        "high": "📈 Высокий",
        "normal": "📊 Нормальный",
        "low": "📉 Низкий"
    }.get(context['volume'], "📊 Нормальный")

    volatility_emoji = {
        "high": "⚡️ Высокая",
        "normal": "📊 Нормальная",
        "low": "💤 Низкая"
    }.get(context['volatility'], "📊 Нормальная")

    context_message = SignalTemplates.MARKET_CONTEXT.format(
        trend=trend_emoji,
        volume=volume_emoji,
        volatility=volatility_emoji
    )

    return message + "\n" + context_message
