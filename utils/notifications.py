# utils/notifications.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime
from utils.database import get_tasks, get_users_by_role_id, get_notifications, add_notification, async_session, task_notifications_table, role_users_table
from aiogram import Bot
import logging
import asyncio

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.scheduler.configure({'event_loop': asyncio.get_event_loop()})  # Привязываем к текущему циклу событий
        logger.info(f"Scheduler initialized: {self.scheduler}")
        self.running = False

    def start(self):
        """Запуск планировщика уведомлений"""
        logger.info(f"Before start, scheduler: {self.scheduler}")
        if not self.running:
            self.scheduler.start()  # Убираем await, так как это синхронный метод
            self.running = True
            logger.info("Планировщик уведомлений запущен")
            asyncio.create_task(self.schedule_existing_tasks())  # Запускаем асинхронно

    async def shutdown(self):
        """Остановка планировщика"""
        if self.running:
            self.scheduler.shutdown()
            self.running = False
            logger.info("Планировщик уведомлений остановлен")
        
    async def schedule_existing_tasks(self):
        """Планирование уведомлений для существующих задач"""
        tasks = await get_tasks()
        logger.info(f"Загружено {len(tasks)} задач для планирования")
        for task in tasks:
            await self.process_task(task)

    async def process_task(self, task):
        """Обработка задачи и планирование уведомлений"""
        logger.info(f"Обрабатывается задача {task.task_id}: notified={task.notified}, due_at={task.due_at}")
        if task.notified == 0 and task.due_at:
            await self.schedule_task_notification(task.task_id, task.due_at, task.description, task.role_id)

    async def schedule_task_notification(self, task_id: int, due_at: datetime, description: str, role_id: str, notification_id=None):
        logger.info(f"Планирование задачи {task_id}: due_at={due_at}, repeat_interval=None")
        
        # Получаем всех пользователей в зависимости от role_id
        if role_id == "all":
            async with async_session() as session:
                result = await session.execute(role_users_table.select())
                users = result.fetchall()
        else:
            users = await get_users_by_role_id(role_id)
        
        if not users:
            logger.warning(f"Для роли {role_id} нет пользователей для уведомления")
            return

        async def send_notification():
            message = f"Напоминание: задача #{task_id}\nОписание: {description}\nДедлайн: {due_at.strftime('%H:%M %d.%m.%Y')}"
            for user in users:
                try:
                    await self.bot.send_message(user.user_id, message)
                    logger.info(f"Уведомление отправлено пользователю {user.user_id}")
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления пользователю {user.user_id}: {e}")
            
            # Обновляем статус уведомления
            async with async_session() as session:
                await session.execute(
                    task_notifications_table.update()
                    .where(task_notifications_table.c.task_id == task_id)
                    .where(task_notifications_table.c.id == notification_id)
                    .values(status='sent')
                )
                await session.commit()
            logger.info(f"Уведомление для задачи {task_id} отправлено")

        job_id = f"task_{task_id}_notification_{notification_id or 'deadline'}"
        self.scheduler.add_job(
            send_notification,
            trigger=DateTrigger(run_date=due_at),
            id=job_id,
            replace_existing=True
        )
        logger.info(f"Запланировано уведомление для {task_id} на {due_at} с ID {job_id}")

    async def add_notification(self, task_id: int, notification_type: str, scheduled_time: datetime = None):
        await add_notification(task_id, notification_type, scheduled_time)
        tasks = await get_tasks(role_id=None)
        task = next((t for t in tasks if t.task_id == task_id), None)
        if task:
            notifications = await get_notifications(task_id)
            latest_notification = notifications[-1] if notifications else None
            await self.schedule_task_notification(task.task_id, scheduled_time or task.due_at, task.description, task.role_id, latest_notification.id if latest_notification else None)

    # ... (остальной код) ...

def init_notifications(bot: Bot):
    """Инициализация сервиса уведомлений"""
    return NotificationService(bot)