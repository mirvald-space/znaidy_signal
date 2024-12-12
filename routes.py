# routes.py

import json
import logging
from datetime import datetime
from typing import Any, Dict

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

logger = logging.getLogger(__name__)


class Routes:
    def __init__(self, bot: Bot, dp: Dispatcher, webhook_path: str, background_tasks=None):
        """
        Инициализация маршрутов
        :param bot: Экземпляр бота
        :param dp: Диспетчер
        :param webhook_path: Путь для вебхука
        :param background_tasks: Экземпляр фоновых задач
        """
        self.bot = bot
        self.dp = dp
        self.webhook_path = webhook_path
        self.background_tasks = background_tasks
        self.start_time = datetime.now()

    async def handle_webhook(self, request: web.Request) -> web.Response:
        """
        Обработчик вебхука от Telegram
        """
        try:
            # Создаем обработчик вебхука
            handler = SimpleRequestHandler(
                dispatcher=self.dp,
                bot=self.bot,
                secret_token=self.bot.token
            )

            # Обрабатываем запрос
            return await handler.handle(request)

        except Exception as e:
            logger.error("Error handling webhook: %s", str(e))
            return web.Response(status=500)

    async def health_check(self, request: web.Request) -> web.Response:
        """
        Эндпоинт проверки здоровья приложения
        """
        try:
            uptime = (datetime.now() - self.start_time).total_seconds()

            health_data = {
                "status": "healthy",
                "uptime": uptime,
                "timestamp": datetime.now().isoformat(),
                "webhook": {
                    "path": self.webhook_path,
                    "active": True
                }
            }

            # Добавляем статус фоновых задач если они доступны
            if self.background_tasks:
                tasks_status = await self.background_tasks.get_status()
                health_data["background_tasks"] = tasks_status

            return web.json_response(health_data)

        except Exception as e:
            logger.error("Health check failed: %s", str(e))
            return web.json_response(
                {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                },
                status=500
            )

    async def get_stats(self, request: web.Request) -> web.Response:
        """
        Эндпоинт для получения статистики
        """
        try:
            if self.background_tasks:
                stats = await self.background_tasks.get_stats()
                return web.json_response(stats)
            return web.json_response({"error": "Statistics not available"}, status=404)
        except Exception as e:
            logger.error("Error getting stats: %s", str(e))
            return web.json_response({"error": str(e)}, status=500)

    async def handle_metrics(self, request: web.Request) -> web.Response:
        """
        Эндпоинт для Prometheus метрик
        """
        try:
            if not self.background_tasks:
                return web.Response(text="# No metrics available", content_type="text/plain")

            stats = await self.background_tasks.get_stats()

            metrics = [
                "# HELP trading_bot_subscribers_total Total number of subscribers",
                "# TYPE trading_bot_subscribers_total gauge",
                f"trading_bot_subscribers_total {
                    stats.get('subscribers_count', 0)}",

                "# HELP trading_bot_signals_total Total number of signals",
                "# TYPE trading_bot_signals_total counter",
                f"trading_bot_signals_total {stats.get('total_signals', 0)}",

                "# HELP trading_bot_analysis_duration_seconds Analysis cycle duration",
                "# TYPE trading_bot_analysis_duration_seconds gauge",
                f"trading_bot_analysis_duration_seconds {
                    stats.get('analysis_duration', 0)}"
            ]

            return web.Response(
                text="\n".join(metrics),
                content_type="text/plain"
            )

        except Exception as e:
            logger.error("Error generating metrics: %s", str(e))
            return web.Response(
                text="# Error generating metrics",
                content_type="text/plain",
                status=500
            )

    def setup_routes(self, app: web.Application):
        """
        Настройка всех маршрутов приложения
        """
        # Основные маршруты
        app.router.add_post(self.webhook_path, self.handle_webhook)
        app.router.add_get("/health", self.health_check)
        app.router.add_get("/stats", self.get_stats)
        app.router.add_get("/metrics", self.handle_metrics)

        # Дополнительные маршруты
        app.router.add_get("/", self.handle_root)
        app.router.add_get("/version", self.handle_version)

        logger.info("Routes configured successfully")

    async def handle_root(self, request: web.Request) -> web.Response:
        """
        Корневой маршрут с базовой информацией
        """
        return web.json_response({
            "name": "Trading Bot API",
            "version": "1.0.0",
            "status": "running",
            "endpoints": [
                "/health",
                "/stats",
                "/metrics",
                "/version"
            ]
        })

    async def handle_version(self, request: web.Request) -> web.Response:
        """
        Информация о версии приложения
        """
        return web.json_response({
            "version": "1.0.0",
            "build_date": "2024-12-13",
            "python_version": "3.9+",
            "aiogram_version": "3.0.0"
        })


# Пример использования в app.py:
"""
from routes import Routes

def create_app():
    app = web.Application()
    
    # Создаем маршруты
    routes = Routes(bot, dp, WEBHOOK_PATH, background_tasks)
    routes.setup_routes(app)
    
    return app
"""
