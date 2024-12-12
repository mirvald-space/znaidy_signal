# trading/signal_formatter.py
def format_signal_message(analysis_result: dict) -> str:
    """Форматирует результаты анализа в читаемое сообщение"""

    if not analysis_result or 'symbol' not in analysis_result:
        return "Ошибка анализа"

    message_parts = [
        f"💹 {analysis_result['symbol']} Анализ",
        f"⏰ {analysis_result['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}",
        f"💵 Цена: {analysis_result['latest_price']:.2f}",
        f"📊 Объем: {analysis_result['latest_volume']:.2f}",
        "",
        "🔍 Рыночный контекст:",
        f"- Тренд: {analysis_result['context']['trend']}",
        f"- Сила тренда: {analysis_result['context']['strength']:.2f}",
        f"- Волатильность: {analysis_result['context']['volatility']}",
        f"- Статус объема: {analysis_result['context']['volume']}",
        f"- Подходит для торговли: {
            '✅' if analysis_result['context']['suitable_for_trading'] else '❌'}",
    ]

    if analysis_result['signals']:
        message_parts.extend([
            "",
            "🎯 Сигналы:",
        ])
        for signal in analysis_result['signals']:
            message_parts.extend([
                f"Тип: {signal['type'].upper()}",
                f"Причина: {signal['reason']}",
                f"Вход: {signal['entry']:.2f}",
                f"Стоп-лосс: {signal['stop_loss']:.2f}",
                f"Тейк-профит: {signal['take_profit']:.2f}",
                f"Сила сигнала: {signal['strength']:.2f}",
                ""
            ])
    else:
        message_parts.extend(["", "🔴 Нет активных сигналов"])

    return "\n".join(message_parts)
