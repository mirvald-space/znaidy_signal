from datetime import datetime
import logging
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

logger = logging.getLogger(__name__)


class Routes:
    def __init__(self, bot: Bot, dp: Dispatcher, webhook_path: str):
        """
        Инициализация маршрутов
        Args:
            bot: Экземпляр бота
            dp: Диспетчер
            webhook_path: Путь для вебхука
        """
        self.bot = bot
        self.dp = dp
        self.webhook_path = webhook_path
        self.start_time = datetime.now()

    async def handle_webhook(self, request: web.Request) -> web.Response:
        """Обработчик вебхука от Telegram"""
        try:
            handler = SimpleRequestHandler(
                dispatcher=self.dp,
                bot=self.bot,
            )
            return await handler.handle(request)
        except Exception as e:
            logger.error(f"Error handling webhook: {str(e)}")
            return web.Response(status=500)

    async def health_check(self, request: web.Request) -> web.Response:
        """Эндпоинт проверки здоровья приложения"""
        try:
            uptime = (datetime.now() - self.start_time).total_seconds()
            webhook_info = await self.bot.get_webhook_info()

            health_data = {
                "status": "healthy",
                "uptime": uptime,
                "timestamp": datetime.now().isoformat(),
                "webhook": {
                    "path": self.webhook_path,
                    "url": webhook_info.url,
                    "active": webhook_info.url is not None
                }
            }
            return web.json_response(health_data)
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return web.json_response(
                {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                },
                status=500
            )

    async def handle_root(self, request: web.Request) -> web.Response:
        """Корневой маршрут с базовой информацией"""
        return web.json_response({
            "name": "Trading Bot API",
            "version": "1.0.0",
            "status": "running",
            "endpoints": [
                "/",
                "/health",
                self.webhook_path
            ]
        })

    def setup_routes(self, app: web.Application):
        """Настройка всех маршрутов приложения"""
        app.router.add_post(self.webhook_path, self.handle_webhook)
        app.router.add_get("/health", self.health_check)
        app.router.add_get("/", self.handle_root)
        logger.info("Routes configured successfully")
