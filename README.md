# Crypto Trading Signal Bot 🤖

Telegram бот для анализа криптовалютных пар и отправки торговых сигналов. Бот использует технические индикаторы (RSI, SMA, Bollinger Bands) для анализа рынка и поиска потенциальных точек входа.

## 🚀 Возможности

- Анализ криптовалютных пар в реальном времени
- Определение тренда и рыночного контекста
- Поиск точек входа на основе технических индикаторов
- Отправка сигналов в Telegram
- Подробное логирование всех операций

## 📋 Требования

- Python 3.8+
- Telegram Bot Token
- Доступ к Binance API

## 🛠 Установка

1. Клонируйте репозиторий:

```bash
git clone <repository-url>
cd trading_bot
```

2. Создайте виртуальное окружение:

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Установите зависимости:

```bash
pip install -r requirements.txt
```

4. Создайте файл .env в корневой директории:

```env
BOT_TOKEN=your_telegram_bot_token
```

## 📁 Структура проекта

```
trading_bot/
├── .env
├── requirements.txt
├── main.py
├── bot.py
├── config.py
├── trading/
│   ├── __init__.py
│   ├── trading_system.py
│   └── signal_formatter.py
└── utils/
    ├── __init__.py
    └── logger.py
```

## 🚦 Запуск

1. Активируйте виртуальное окружение:

```bash
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

2. Запустите бота:

```bash
python main.py
```

## 📱 Использование

Бот поддерживает следующие команды:

- `/start` - Подписаться на сигналы
- `/stop` - Отписаться от сигналов
- `/status` - Показать текущий статус системы
- `/symbols` - Список отслеживаемых пар

## 📊 Торговые сигналы

Бот анализирует следующие индикаторы:

- RSI (Relative Strength Index)
- SMA (Simple Moving Average)
- Bollinger Bands
- Объем торгов
- Волатильность

Сигналы генерируются на основе:

- Отскоков от уровней перекупленности/перепроданности RSI
- Пересечений границ Bollinger Bands
- Анализа объемов торгов
- Оценки волатильности

## 🔍 Мониторинг

Бот создает подробные логи в директории `logs/`. Каждый файл лога содержит:

- Результаты анализа
- Найденные сигналы
- Ошибки и предупреждения
- Статистику работы

## 🛡 Безопасность

- Храните токен бота в файле .env
- Не публикуйте токен в публичном доступе
- Регулярно проверяйте логи на наличие ошибок

## 🔧 Конфигурация

Основные параметры можно настроить в файлах:

- `config.py` - Конфигурация бота
- `trading_system.py` - Параметры технического анализа
- `bot.py` - Настройки Telegram бота

## 🤝 Вклад в проект

1. Форкните репозиторий
2. Создайте ветку для новой функции
3. Внесите изменения
4. Отправьте пулл-реквест

## 📝 Планы по развитию

- [ ] Добавить базу данных для хранения подписчиков
- [ ] Реализовать настройку параметров анализа через команды
- [ ] Добавить статистику успешности сигналов
- [ ] Реализовать бэктестинг стратегий
- [ ] Добавить поддержку дополнительных индикаторов

## ⚠️ Дисклеймер

Этот бот предназначен только для образовательных целей. Торговля криптовалютами сопряжена с высокими рисками. Всегда проводите собственный анализ перед принятием торговых решений.

## 📄 Лицензия

MIT License
