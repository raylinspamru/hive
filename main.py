# main.py
import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import settings
from bot.handlers import router as handlers_router
from bot.adminpanel import adminpanel_router
from bot.basic_handlers import router as basic_router
from utils.database import engine as async_engine, init_db
from utils.notifications import init_notifications
from web import app as quart_app, set_notification_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

async def main():
    logging.info("Инициализация базы данных...")
    await init_db()

    dp.include_router(basic_router)
    dp.include_router(adminpanel_router)
    dp.include_router(handlers_router)

    notifications = init_notifications(bot)
    set_notification_service(notifications)

    notifications.start()  # Синхронный вызов, так как start() больше не корутина

    web_task = asyncio.create_task(quart_app.run_task(host='localhost', port=5000, debug=True))
    polling_task = asyncio.create_task(dp.start_polling(bot, skip_updates=True))

    logging.info("Бот и веб-интерфейс запущены!")
    try:
        await asyncio.gather(web_task, polling_task)
    except KeyboardInterrupt:
        logging.info("Завершаем работу...")
        await notifications.shutdown()
        web_task.cancel()
        polling_task.cancel()
        await bot.session.close()
        await async_engine.dispose()
        await asyncio.sleep(1)
    finally:
        logging.info("Бот и веб-интерфейс остановлены.")

if __name__ == "__main__":
    asyncio.run(main())