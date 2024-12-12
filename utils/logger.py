# utils/logger.py
import logging
import os
from datetime import datetime


def setup_logger():
    # Создаем директорию для логов если её нет
    logs_dir = 'logs'
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    # Текущая дата для имени файла
    current_date = datetime.now().strftime('%Y-%m-%d')
    log_file = f'{logs_dir}/trading_{current_date}.log'

    # Настройка форматирования
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
    )

    # Файловый обработчик
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Настройка корневого логгера
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
