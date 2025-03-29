#utils/database.py:
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import MetaData, Table, Column, String, Integer, Text, DateTime, ForeignKey
from config import settings
from datetime import datetime, timedelta
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = settings.DATABASE_URL
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

metadata = MetaData()

# Таблица ролей
roles_table = Table(
    "roles",
    metadata,
    Column("role_id", String, primary_key=True),
    Column("role_group", String, nullable=True),
    Column("role_group_name", String, nullable=True),
    Column("role_subgroup", String, nullable=True),
    Column("role_full_name", String, nullable=False),
    Column("rolepass", String, nullable=False),
)

# Таблица пользователей ролей
role_users_table = Table(
    "role_users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("role_id", String, nullable=False),
    Column("user_id", String, nullable=False),
    Column("user_name", String, nullable=True),
)

# Таблица задач
tasks_table = Table(
    "tasks",
    metadata,
    Column("task_id", Integer, primary_key=True, autoincrement=True),
    Column("role_id", String, nullable=False),
    Column("description", String, nullable=False),
    Column("status", String, nullable=False),
    Column("created_at", DateTime, nullable=False),
    Column("due_at", DateTime, nullable=True),
    Column("repeat_interval", String, nullable=True),
    Column("notified", Integer, default=0),
)

# Таблица кнопок для динамического меню
buttons_table = Table(
    "buttons",
    metadata,
    Column("data", String, primary_key=True),
    Column("command", Integer, nullable=False),
    Column("parentdataorcommand", String, nullable=False),
    Column("name", String, nullable=False),
    Column("type", String, nullable=False),
    Column("text", Text, nullable=True),
    Column("submdata1", String, nullable=True),
    Column("submdata2", String, nullable=True),
    Column("submdata3", String, nullable=True),
    Column("submdata4", String, nullable=True),
    Column("submdata5", String, nullable=True),
    Column("submdata6", String, nullable=True),
    Column("submdata7", String, nullable=True),
    Column("submdata8", String, nullable=True),
    Column("submdata9", String, nullable=True),
    Column("submdata10", String, nullable=True),
    Column("submdata11", String, nullable=True),
    Column("submdata12", String, nullable=True),
    Column("submdata13", String, nullable=True),
    Column("submdata14", String, nullable=True),
    Column("submdata15", String, nullable=True),
)

# Таблица завершённых задач
task_completions_table = Table(
    "task_completions",
    metadata,
    Column("task_id", Integer, ForeignKey("tasks.task_id"), primary_key=True),
    Column("user_id", String, ForeignKey("role_users.user_id"), primary_key=True),
    Column("status", String, nullable=False, default="accepted"),
    Column("completed_at", DateTime, nullable=True),
)

# Таблица уведомлений
task_notifications_table = Table(
    "task_notifications",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("task_id", Integer, ForeignKey("tasks.task_id"), nullable=False),
    Column("type", String, nullable=False),
    Column("scheduled_time", DateTime, nullable=True),
    Column("repeat_interval", String, nullable=True),
    Column("start_offset_value", Integer, nullable=True),
    Column("start_offset_unit", String, nullable=True),
    Column("end_offset_value", Integer, nullable=True),
    Column("end_offset_unit", String, nullable=True),
    Column("fixed_times", String, nullable=True),
    Column("status", String, nullable=False, default="scheduled"),
)

# Инициализация базы данных
async def init_db():
    logger.info("Инициализация базы данных...")
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

        # Проверка существующих данных
        roles_exist = (await conn.execute(roles_table.select().limit(1))).fetchone() is not None
        tasks_exist = (await conn.execute(tasks_table.select().limit(1))).fetchone() is not None
        buttons_exist = (await conn.execute(buttons_table.select().limit(1))).fetchone() is not None
        completions_exist = (await conn.execute(task_completions_table.select().limit(1))).fetchone() is not None
        notifications_exist = (await conn.execute(task_notifications_table.select().limit(1))).fetchone() is not None

        if not roles_exist:
            logger.info("Добавление тестовых ролей...")
            await conn.execute(
                roles_table.insert(),
                [
                    {"role_id": "r1", "role_group": "voz", "role_group_name": "Вожатый", "role_subgroup": "1", "role_full_name": "Вожатый 1-го отряда", "rolepass": "pass_voz_1"},
                    {"role_id": "r2", "role_group": "voz", "role_group_name": "Вожатый", "role_subgroup": "2", "role_full_name": "Вожатый 2-го отряда", "rolepass": "pass_voz_2"},
                    {"role_id": "r14", "role_group": None, "role_group_name": "Диджей", "role_subgroup": None, "role_full_name": "Диджей", "rolepass": "dj2025"},
                ]
            )
            await conn.execute(
                role_users_table.insert(),
                [
                    {"role_id": "r1", "user_id": "5760551190", "user_name": "Иван Иванов"},
                    {"role_id": "r2", "user_id": "1234567890", "user_name": "Пётр Петров"},
                    {"role_id": "r14", "user_id": "9876543210", "user_name": "Анна Сидорова"},
                ]
            )

        if not tasks_exist:
            logger.info("Добавление тестовых задач...")
            await conn.execute(
                tasks_table.insert(),
                [
                    {"role_id": "voz", "description": "Провести собрание вожатых", "status": "accepted", "created_at": datetime.now(), "due_at": datetime.now() + timedelta(days=1), "repeat_interval": None, "notified": 0},
                    {"role_id": "r14", "description": "Подготовить плейлист", "status": "sent", "created_at": datetime.now(), "due_at": datetime.now() + timedelta(hours=5), "repeat_interval": None, "notified": 0},
                ]
            )

        if not buttons_exist:
            logger.info("Добавление тестовых кнопок...")
            await conn.execute(
                buttons_table.insert(),
                [
                    {
                        "data": "voz",
                        "command": 0,
                        "parentdataorcommand": "start",
                        "name": "Главное меню вожатых",
                        "type": "menu",
                        "text": "Меню для вожатых",
                        "submdata1": "voz_info",
                        "submdata2": "voz_link",
                        "submdata3": None,
                        "submdata4": None,
                        "submdata5": None,
                        "submdata6": None,
                        "submdata7": None,
                        "submdata8": None,
                        "submdata9": None,
                        "submdata10": None,
                        "submdata11": None,
                        "submdata12": None,
                        "submdata13": None,
                        "submdata14": None,
                        "submdata15": None,
                    },
                    {
                        "data": "voz_info",
                        "command": 0,
                        "parentdataorcommand": "voz",
                        "name": "Информация",
                        "type": "text",
                        "text": "Вы - вожатый! Ваша задача - вдохновлять детей.",
                        "submdata1": None,
                        "submdata2": None,
                        "submdata3": None,
                        "submdata4": None,
                        "submdata5": None,
                        "submdata6": None,
                        "submdata7": None,
                        "submdata8": None,
                        "submdata9": None,
                        "submdata10": None,
                        "submdata11": None,
                        "submdata12": None,
                        "submdata13": None,
                        "submdata14": None,
                        "submdata15": None,
                    },
                    {
                        "data": "voz_link",
                        "command": 0,
                        "parentdataorcommand": "voz",
                        "name": "Полезная ссылка",
                        "type": "url",
                        "text": "https://example.com",
                        "submdata1": None,
                        "submdata2": None,
                        "submdata3": None,
                        "submdata4": None,
                        "submdata5": None,
                        "submdata6": None,
                        "submdata7": None,
                        "submdata8": None,
                        "submdata9": None,
                        "submdata10": None,
                        "submdata11": None,
                        "submdata12": None,
                        "submdata13": None,
                        "submdata14": None,
                        "submdata15": None,
                    },
                ]
            )

        if not completions_exist:
            logger.info("Добавление тестовых данных в task_completions...")
            await conn.execute(
                task_completions_table.insert(),
                [
                    {"task_id": 1, "user_id": "5760551190", "status": "completed", "completed_at": datetime.now()},
                    {"task_id": 1, "user_id": "1234567890", "status": "accepted", "completed_at": None},
                ]
            )

        if not notifications_exist:
            logger.info("Добавление тестовых уведомлений...")
            await conn.execute(
                task_notifications_table.insert(),
                [
                    {"task_id": 1, "type": "deadline", "scheduled_time": datetime.now() + timedelta(days=1), "repeat_interval": None, "start_offset": None, "end_offset": None, "fixed_times": None, "status": "scheduled"},
                ]
            )

        await conn.commit()
    logger.info("База данных инициализирована.")

# Функции для работы с базой данных
async def get_role_by_password(password: str):
    async with async_session() as session:
        result = await session.execute(roles_table.select().where(roles_table.c.rolepass == password))
        return result.fetchone()

async def get_role_by_id(role_id: str):
    async with async_session() as session:
        result = await session.execute(roles_table.select().where(roles_table.c.role_id == role_id))
        return result.fetchone()

async def get_roles():
    async with async_session() as session:
        result = await session.execute(roles_table.select())
        return result.fetchall()

async def bind_user_to_role(user_id: str, role_id: str, user_name: str = None):
    async with async_session() as session:
        await session.execute(
            role_users_table.insert().values(user_id=user_id, role_id=role_id, user_name=user_name)
        )
        await session.commit()

async def get_user_role(user_id: str):
    async with async_session() as session:
        result = await session.execute(role_users_table.select().where(role_users_table.c.user_id == user_id))
        return result.fetchone()

async def unbind_user_from_role(user_id: str):
    async with async_session() as session:
        await session.execute(role_users_table.delete().where(role_users_table.c.user_id == user_id))
        await session.commit()

async def get_tasks(role_id: str = None, role_group: str = None, all_tasks: bool = False):
    async with async_session() as session:
        if all_tasks:
            result = await session.execute(tasks_table.select().where(tasks_table.c.role_id == "all"))
            return result.fetchall()
        elif role_group:
            result = await session.execute(tasks_table.select().where(tasks_table.c.role_id == role_group))
            return result.fetchall()
        elif role_id:
            result = await session.execute(tasks_table.select().where(tasks_table.c.role_id == role_id))
            return result.fetchall()
        return []

async def update_task_status(task_id: int, new_status: str):
    async with async_session() as session:
        await session.execute(
            tasks_table.update().where(tasks_table.c.task_id == task_id).values(status=new_status)
        )
        await session.commit()

async def get_button_by_data(data: str):
    async with async_session() as session:
        result = await session.execute(buttons_table.select().where(buttons_table.c.data == data))
        return result.fetchone()

async def get_users_by_role_id(role_id: str):
    async with async_session() as session:
        result = await session.execute(role_users_table.select().where(role_users_table.c.role_id == role_id))
        return result.fetchall()

async def add_task_completion(task_id: int, user_id: str, status: str = "accepted", completed_at=None):
    async with async_session() as session:
        result = await session.execute(
            task_completions_table.select()
            .where(task_completions_table.c.task_id == task_id)
            .where(task_completions_table.c.user_id == user_id)
        )
        existing_record = result.fetchone()

        if existing_record:
            await session.execute(
                task_completions_table.update()
                .where(task_completions_table.c.task_id == task_id)
                .where(task_completions_table.c.user_id == user_id)
                .values(status=status, completed_at=completed_at)
            )
        else:
            await session.execute(
                task_completions_table.insert().values(
                    task_id=task_id,
                    user_id=user_id,
                    status=status,
                    completed_at=completed_at
                )
            )
        await session.commit()

async def get_task_completions(task_id: int):
    async with async_session() as session:
        result = await session.execute(
            task_completions_table.select()
            .join(role_users_table, task_completions_table.c.user_id == role_users_table.c.user_id)
            .join(roles_table, role_users_table.c.role_id == roles_table.c.role_id)
            .where(task_completions_table.c.task_id == task_id)
        )
        return result.fetchall()

async def add_task(role_id: str, description: str, status: str, due_at: DateTime = None, repeat_interval: str = None):
    async with async_session() as session:
        result = await session.execute(
            tasks_table.insert().values(
                role_id=role_id,
                description=description,
                status=status,
                created_at=datetime.now(),
                due_at=due_at,
                repeat_interval=repeat_interval,
                notified=0
            )
        )
        await session.commit()
        return result.inserted_primary_key[0]

async def add_notification(task_id: int, type: str, scheduled_time: DateTime = None, repeat_interval: str = None,
                          start_offset_value: int = None, start_offset_unit: str = None,
                          end_offset_value: int = None, end_offset_unit: str = None, fixed_times: str = None):
    async with async_session() as session:
        await session.execute(
            task_notifications_table.insert().values(
                task_id=task_id,
                type=type,
                scheduled_time=scheduled_time,
                repeat_interval=repeat_interval,
                start_offset_value=start_offset_value,
                start_offset_unit=start_offset_unit,
                end_offset_value=end_offset_value,
                end_offset_unit=end_offset_unit,
                fixed_times=fixed_times,
                status="scheduled"
            )
        )
        await session.commit()

async def get_notifications(task_id: int):
    async with async_session() as session:
        result = await session.execute(
            task_notifications_table.select().where(task_notifications_table.c.task_id == task_id)
        )
        return result.fetchall()

if __name__ == "__main__":
    import asyncio
    asyncio.run(init_db())