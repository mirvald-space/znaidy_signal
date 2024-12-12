# trading/signal_formatter.py
from datetime import datetime
from string import Template
from typing import Any, Dict


class SignalTemplate:
    # Базовые шаблоны для разных частей сообщения
    HEADER = Template("""💹 $symbol Анализ
⏰ $timestamp
💵 Цена: $price
📊 Объем: $volume""")

    MARKET_CONTEXT = Template("""
🔍 Рыночный контекст:
- Тренд: $trend
- Сила тренда: $trend_strength
- Волатильность: $volatility
- Статус объема: $volume_status
- Подходит для торговли: $suitable""")

    SIGNAL = Template("""
Тип: $type
Причина: $reason
Вход: $entry
Стоп-лосс: $stop_loss
Тейк-профит: $take_profit
Сила сигнала: $strength""")


def format_signal_message(analysis_result: Dict[str, Any]) -> str:
    """Форматирует результаты анализа в читаемое сообщение используя Template strings"""

    if not analysis_result or 'symbol' not in analysis_result:
        return "Ошибка анализа"

    # Форматируем заголовок
    header = SignalTemplate.HEADER.substitute(
        symbol=analysis_result['symbol'],
        timestamp=analysis_result['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
        price='{:.2f}'.format(analysis_result['latest_price']),
        volume='{:.2f}'.format(analysis_result['latest_volume'])
    )

    # Форматируем рыночный контекст
    context = SignalTemplate.MARKET_CONTEXT.substitute(
        trend=analysis_result['context']['trend'],
        trend_strength='{:.2f}'.format(analysis_result['context']['strength']),
        volatility=analysis_result['context']['volatility'],
        volume_status=analysis_result['context']['volume'],
        suitable='✅' if analysis_result['context']['suitable_for_trading'] else '❌'
    )

    # Формируем полное сообщение
    message_parts = [header, context]

    # Добавляем сигналы если они есть
    if analysis_result['signals']:
        message_parts.append("\n🎯 Сигналы:")
        for signal in analysis_result['signals']:
            signal_text = SignalTemplate.SIGNAL.substitute(
                type=signal['type'].upper(),
                reason=signal['reason'],
                entry='{:.2f}'.format(signal['entry']),
                stop_loss='{:.2f}'.format(signal['stop_loss']),
                take_profit='{:.2f}'.format(signal['take_profit']),
                strength='{:.2f}'.format(signal['strength'])
            )
            message_parts.append(signal_text)
    else:
        message_parts.append("\n🔴 Нет активных сигналов")

    return "\n".join(message_parts)


# Пример использования:
if __name__ == "__main__":
    # Тестовые данные
    test_data = {
        'symbol': 'BTCUSDT',
        'timestamp': datetime.now(),
        'latest_price': 50000.00,
        'latest_volume': 1000.00,
        'context': {
            'trend': 'uptrend',
            'strength': 0.75,
            'volatility': 'normal',
            'volume': 'high',
            'suitable_for_trading': True
        },
        'signals': [{
            'type': 'long',
            'reason': 'RSI bounce',
            'entry': 50000.00,
            'stop_loss': 49500.00,
            'take_profit': 51000.00,
            'strength': 0.8
        }]
    }

    formatted_message = format_signal_message(test_data)
    print(formatted_message)
