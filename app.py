# app.py

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.types import WebhookInfo
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from handlers import BotHandlers

from background_tasks import BackgroundTasks
from config import load_config

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
config = load_config()
WEBHOOK_HOST = os.environ.get("WEBHOOK_URL", "https://your-app.onrender.com")
WEBHOOK_PATH = f"/webhook/{config.tg_bot.token}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
PORT = int(os.environ.get("PORT", 8080))

# Символы для мониторинга
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
UPDATE_INTERVAL = 300  # 5 минут


class TradingBotApp:
    def __init__(self):
        self.bot = Bot(token=config.tg_bot.token)
        self.dp = Dispatcher()
        self.handlers = None
        self.background_tasks = None
        self.app = None

    async def setup_webhook(self):
        """Настройка вебхука"""
        try:
            webhook_info = await self.bot.get_webhook_info()
            if webhook_info.url != WEBHOOK_URL:
                await self.bot.set_webhook(
                    url=WEBHOOK_URL,
                    allowed_updates=webhook_info.allowed_updates
                )
                logger.info("Webhook set to: %s", WEBHOOK_URL)
        except Exception as e:
            logger.error("Failed to set webhook: %s", str(e))
            raise

    async def on_startup(self, app: web.Application):
        """Действия при запуске приложения"""
        try:
            # Настройка вебхука
            await self.setup_webhook()

            # Запуск фоновых задач
            await self.background_tasks.start()

            logger.info("Application startup completed successfully")
        except Exception as e:
            logger.error("Error during startup: %s", str(e))
            raise

    async def on_shutdown(self, app: web.Application):
        """Действия при остановке приложения"""
        try:
            # Останавливаем фоновые задачи
            await self.background_tasks.stop()

            # Удаляем вебхук
            await self.bot.delete_webhook()

            # Закрываем соединения
            await self.bot.session.close()

            logger.info("Application shutdown completed successfully")
        except Exception as e:
            logger.error("Error during shutdown: %s", str(e))

    def setup_routes(self, app: web.Application):
        """Настройка маршрутов"""
        # Создаем обработчик вебхука
        webhook_handler = SimpleRequestHandler(
            dispatcher=self.dp,
            bot=self.bot,
            secret_token=config.tg_bot.token
        )

        # Добавляем маршрут для вебхука
        webhook_handler.register(app, path=WEBHOOK_PATH)

        # Добавляем маршрут для проверки здоровья
        app.router.add_get("/health", self.health_check)

    async def health_check(self, request: web.Request):
        """Проверка здоровья приложения"""
        try:
            # Получаем статус фоновых задач
            tasks_status = await self.background_tasks.get_status()

            # Проверяем webhook
            webhook_info = await self.bot.get_webhook_info()

            health_data = {
                "status": "healthy",
                "webhook": {
                    "url": webhook_info.url,
                    "has_custom_certificate": webhook_info.has_custom_certificate,
                    "pending_update_count": webhook_info.pending_update_count
                },
                "background_tasks": tasks_status,
                "subscribers_count": len(self.handlers.get_subscribers())
            }

            return web.json_response(health_data)
        except Exception as e:
            logger.error("Health check failed: %s", str(e))
            return web.json_response(
                {"status": "unhealthy", "error": str(e)},
                status=500
            )

    async def create_app(self):
        """Создание и настройка приложения"""
        try:
            # Инициализация компонентов
            self.handlers = BotHandlers(self.bot, SYMBOLS, UPDATE_INTERVAL)
            self.dp.include_router(self.handlers.get_router())

            self.background_tasks = BackgroundTasks(
                self.bot,
                SYMBOLS,
                UPDATE_INTERVAL,
                self.handlers.get_subscribers()
            )

            # Создание приложения
            app = web.Application()

            # Настройка маршрутов
            self.setup_routes(app)

            # Добавляем обработчики запуска/остановки
            app.on_startup.append(self.on_startup)
            app.on_shutdown.append(self.on_shutdown)

            return app
        except Exception as e:
            logger.error("Failed to create application: %s", str(e))
            raise


async def start_app():
    """Запуск приложения"""
    try:
        # Создаем экземпляр приложения
        trading_bot = TradingBotApp()
        app = await trading_bot.create_app()

        # Настраиваем runner
        runner = web.AppRunner(app)
        await runner.setup()

        # Запускаем сайт
        site = web.TCPSite(runner, host='0.0.0.0', port=PORT)
        await site.start()

        logger.info("Application started on port %d", PORT)

        # Держим приложение запущенным
        try:
            await asyncio.Event().wait()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Shutting down...")
        finally:
            await runner.cleanup()

    except Exception as e:
        logger.error("Failed to start application: %s", str(e))
        raise

if __name__ == '__main__':
    try:
        asyncio.run(start_app())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error("Application crashed: %s", str(e))
        exit(1)
