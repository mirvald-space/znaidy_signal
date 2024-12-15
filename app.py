import asyncio
import logging
from string import Template
from typing import Optional

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from background_tasks import BackgroundTasks
from config import Config, load_config
from handlers import BotHandlers
from utils.logger import setup_logger


class LogTemplates:
    WEBHOOK_INFO = Template("Current webhook info: $info")
    SETTING_WEBHOOK = Template("Setting webhook to: $url")
    WEBHOOK_VERIFIED = Template("Verified webhook info: $info")
    WEBHOOK_ERROR = Template("Error setting webhook: $error")
    WEBHOOK_SET = Template("Webhook is already set correctly to: $url")
    STARTUP_ERROR = Template("Error during startup: $error")
    SHUTDOWN_ERROR = Template("Error during shutdown: $error")
    APP_START = Template("Application started on port $port")
    APP_CRASH = Template("Application crashed: $error")


class TradingBotApp:
    def __init__(self, config: Optional[Config] = None):
        """
        Инициализация приложения
        Args:
            config: Конфигурация приложения. Если не указана, загружается из переменных окружения
        """
        self.config = config or load_config()
        self.logger = setup_logger(self.config.logging)

        # Инициализация компонентов бота
        self.bot = Bot(token=self.config.tg_bot.token)
        self.dp = Dispatcher()
        self.handlers = BotHandlers(self.bot, self.config.trading)
        self.dp.include_router(self.handlers.get_router())

        # Инициализация фоновых задач
        self.background_tasks = BackgroundTasks(
            bot=self.bot,
            config=self.config.trading,
            subscribers=self.handlers.get_subscribers()
        )

    async def setup_webhook(self):
        """Настройка вебхука"""
        try:
            webhook_info = await self.bot.get_webhook_info()
            self.logger.info(LogTemplates.WEBHOOK_INFO.substitute(
                info=str(webhook_info)))

            if webhook_info.url != self.config.webhook.url:
                self.logger.info(LogTemplates.SETTING_WEBHOOK.substitute(
                    url=self.config.webhook.url))
                await self.bot.delete_webhook()  # Clear existing webhook first
                # Small delay to ensure webhook is cleared
                await asyncio.sleep(1)

                await self.bot.set_webhook(
                    url=self.config.webhook.url,
                    allowed_updates=['message', 'callback_query'],
                    drop_pending_updates=True
                )
                self.logger.info("Webhook set successfully")
            else:
                self.logger.info(LogTemplates.WEBHOOK_SET.substitute(
                    url=self.config.webhook.url))

            # Verify webhook was set
            new_webhook_info = await self.bot.get_webhook_info()
            self.logger.info(LogTemplates.WEBHOOK_VERIFIED.substitute(
                info=str(new_webhook_info)))
        except Exception as e:
            self.logger.error(LogTemplates.WEBHOOK_ERROR.substitute(
                error=str(e)), exc_info=True)
            raise

    async def on_startup(self, app: web.Application):
        """Действия при запуске приложения"""
        try:
            await self.setup_webhook()
            await self.background_tasks.start()
            self.logger.info("Application startup completed successfully")
        except Exception as e:
            self.logger.error(
                LogTemplates.STARTUP_ERROR.substitute(error=str(e)))
            raise

    async def on_shutdown(self, app: web.Application):
        """Действия при остановке приложения"""
        try:
            await self.background_tasks.stop()
            await self.bot.delete_webhook()
            await self.bot.session.close()
            self.logger.info("Application shutdown completed successfully")
        except Exception as e:
            self.logger.error(
                LogTemplates.SHUTDOWN_ERROR.substitute(error=str(e)))

    async def health_check(self, request: web.Request) -> web.Response:
        """Проверка здоровья приложения"""
        try:
            tasks_status = await self.background_tasks.get_status()
            webhook_info = await self.bot.get_webhook_info()

            health_data = {
                "status": "healthy",
                "webhook": {
                    "url": webhook_info.url,
                    "has_custom_certificate": webhook_info.has_custom_certificate,
                    "pending_update_count": webhook_info.pending_update_count
                },
                "background_tasks": tasks_status,
                "subscribers_count": len(self.handlers.get_subscribers()),
                "symbols": self.config.trading.symbols,
                "update_interval": self.config.trading.update_interval
            }

            return web.json_response(health_data)
        except Exception as e:
            self.logger.error("Health check failed: " + str(e))
            return web.json_response(
                {"status": "unhealthy", "error": str(e)},
                status=500
            )

    def setup_routes(self, app: web.Application):
        """Настройка маршрутов"""
        # Создаем обработчик вебхука
        webhook_handler = SimpleRequestHandler(
            dispatcher=self.dp,
            bot=self.bot,
        )
        # Настраиваем маршруты
        webhook_handler.register(app, path=self.config.webhook.path)
        app.router.add_get("/health", self.health_check)
        app.router.add_get("/", lambda r: web.json_response({
            "name": "Trading Bot API",
            "version": "1.0.0",
            "status": "running"
        }))

    async def create_app(self) -> web.Application:
        """Создание и настройка приложения"""
        app = web.Application()
        self.setup_routes(app)
        app.on_startup.append(self.on_startup)
        app.on_shutdown.append(self.on_shutdown)
        return app

    async def run(self):
        """Запуск приложения"""
        try:
            app = await self.create_app()
            runner = web.AppRunner(app)
            await runner.setup()

            site = web.TCPSite(
                runner,
                host='0.0.0.0',
                port=self.config.webhook.port
            )
            await site.start()

            self.logger.info(LogTemplates.APP_START.substitute(
                port=str(self.config.webhook.port)))

            try:
                await asyncio.Event().wait()
            except (KeyboardInterrupt, SystemExit):
                self.logger.info("Shutting down...")
            finally:
                await runner.cleanup()

        except Exception as e:
            self.logger.error(LogTemplates.APP_CRASH.substitute(error=str(e)))
            raise


if __name__ == '__main__':
    try:
        app = TradingBotApp()
        asyncio.run(app.run())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Application stopped by user")
    except Exception as e:
        logging.error("Application crashed: " + str(e))
        exit(1)
