import logging
import os
from datetime import datetime
from typing import Optional

from config import LoggingConfig


def setup_logger(config: LoggingConfig) -> logging.Logger:
    """
    Настройка логгера приложения
    Args:
        config: Конфигурация логирования
    Returns:
        Настроенный логгер
    """
    # Создаем директорию для логов если её нет
    if not os.path.exists(config.log_dir):
        os.makedirs(config.log_dir)

    # Текущая дата для имени файла
    current_date = datetime.now().strftime('%Y-%m-%d')
    log_file = f'{config.log_dir}/trading_{current_date}.log'

    # Настройка форматирования
    formatter = logging.Formatter(
        config.format,
        datefmt=config.date_format
    )

    # Файловый обработчик
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(config.level)

    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(config.level)

    # Настройка корневого логгера
    logger = logging.getLogger()
    logger.setLevel(config.level)

    # Удаляем существующие обработчики если они есть
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Добавляем новые обработчики
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info(f"Logger initialized. Log file: {log_file}")

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Получение логгера для модуля
    Args:
        name: Имя модуля
    Returns:
        Logger: Настроенный логгер
    """
    return logging.getLogger(name)
