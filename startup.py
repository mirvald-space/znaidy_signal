# startup.py
import asyncio
from logging import logger  # Assuming you're using loguru for logging

from aiohttp import web

import bot
from app import WEBHOOK_URL

# Assuming bot, WEBHOOK_URL, and send_signals are defined elsewhere in your code


async def on_startup(app: web.Application):
    """Действия при запуске"""
    # Устанавливаем вебхук
    webhook_info = await bot.get_webhook_info()
    if webhook_info.url != WEBHOOK_URL:
        await bot.set_webhook(url=WEBHOOK_URL)
    logger.info(f"Webhook set to: {WEBHOOK_URL}")

    # Запускаем фоновую задачу
    app['send_signals_task'] = asyncio.create_task(bot.send_signals())
    logger.info("Background task started")


async def on_shutdown(app: web.Application):
    """Действия при остановке"""
    # Останавливаем фоновую задачу
    app['send_signals_task'].cancel()
    try:
        await app['send_signals_task']
    except asyncio.CancelledError:
        logger.info("Background task cancelled")

    # Удаляем вебхук
    await bot.delete_webhook()
    logger.info("Webhook deleted")

    # Закрываем сессии
    await bot.session.close()
    logger.info("Bot session closed")

    logger.info("Bot shutdown completed")
