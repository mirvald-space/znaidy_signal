# main.py
import asyncio
import logging

from bot import bot, dp, send_signals


async def main():
    logging.info("Starting bot")
    # Запускаем отправку сигналов в фоновом режиме
    asyncio.create_task(send_signals())
    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
