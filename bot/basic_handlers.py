# bot/basic_handlers.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from utils.database import get_role_by_password, bind_user_to_role, get_user_role, get_role_by_id, unbind_user_from_role, get_tasks, update_task_status, get_button_by_data, add_task_completion
from datetime import datetime

router = Router()

# Состояния для FSM
class AuthState(StatesGroup):
    waiting_for_password = State()

class TaskState(StatesGroup):
    viewing_tasks = State()

class ChangeRoleState(StatesGroup):
    confirming = State()

# Главное меню
def get_main_menu(role_group: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Задачи", callback_data="tasks")],
        [InlineKeyboardButton(text="Динамическое меню", callback_data=role_group or "menu")],
        [InlineKeyboardButton(text="Сменить роль", callback_data="change_role")]
    ])

# Обработчик команды /start
@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    role_user = await get_user_role(user_id)
    
    if role_user:
        role = await get_role_by_id(role_user.role_id)
        await message.answer(
            f"Добро пожаловать, {role.role_full_name}! Вот ваше меню:",
            reply_markup=get_main_menu(role.role_group)
        )
    else:
        await message.answer("Введите пароль для входа:")
        await state.set_state(AuthState.waiting_for_password)

# Обработчик ввода пароля
@router.message(AuthState.waiting_for_password)
async def process_password(message: Message, state: FSMContext):
    password = message.text.strip()
    role = await get_role_by_password(password)
    if role:
        user_id = str(message.from_user.id)
        await bind_user_to_role(user_id, role.role_id)
        await message.answer(
            f"Вы вошли как {role.role_full_name}. Вот ваше меню:",
            reply_markup=get_main_menu(role.role_group)
        )
        await state.clear()
    else:
        await message.answer("Введён неверный пароль. Попробуйте снова:")

# Обработчик выбора "Задачи"
@router.callback_query(F.data == "tasks")
async def show_task_categories(callback: CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Личные задачи", callback_data="tasks_personal")],
        [InlineKeyboardButton(text="Задачи для роли", callback_data="tasks_role")],
        [InlineKeyboardButton(text="Общие задачи", callback_data="tasks_all")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_main")]
    ])
    await callback.message.edit_text("Выберите категорию задач:", reply_markup=keyboard)
    await state.set_state(TaskState.viewing_tasks)
    await callback.answer()

# Отображение задач
@router.callback_query(TaskState.viewing_tasks, F.data.startswith("tasks_"))
async def show_tasks(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    role_user = await get_user_role(user_id)
    if not role_user:
        await callback.message.edit_text("Вы не авторизованы. Введите /start для входа.")
        await callback.answer()
        return
    
    role = await get_role_by_id(role_user.role_id)
    category = callback.data.split("_")[1]
    
    tasks = []
    if category == "personal":
        tasks = await get_tasks(role_id=role.role_id)
        tasks = [t for t in tasks if t.role_id == role.role_id]
        title = "Личные задачи"
    elif category == "role" and role.role_group:
        tasks = await get_tasks(role_group=role.role_group)
        tasks = [t for t in tasks if t.role_id == role.role_group]
        title = f"Задачи для роли ({role.role_group})"
    elif category == "all":
        tasks = await get_tasks(all_tasks=True)
        title = "Общие задачи"

    # Сохраняем данные в состоянии
    await state.update_data(tasks=tasks, category=category, title=title, show_completed=False)
    
    # Показываем невыполненные задачи
    incomplete_tasks = [t for t in tasks if t.status != "completed"]
    
    if not incomplete_tasks:
        text = f"{title} (невыполненные):\nНет невыполненных задач."
    else:
        text = f"{title} (невыполненные):\n" + "\n".join(f"#{t.task_id} {t.description}" for t in incomplete_tasks)

    keyboard = InlineKeyboardBuilder()
    for task in incomplete_tasks:
        keyboard.row(InlineKeyboardButton(text=f"Выполнить #{task.task_id}", callback_data=f"complete_{task.task_id}"))
    keyboard.row(InlineKeyboardButton(text="Показать выполненные", callback_data="show_completed"))
    keyboard.row(InlineKeyboardButton(text="Назад", callback_data="tasks"))
    
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await callback.answer()

# Показать выполненные задачи
@router.callback_query(TaskState.viewing_tasks, F.data == "show_completed")
async def show_completed_tasks(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    tasks = data["tasks"]
    title = data["title"]
    
    completed_tasks = [t for t in tasks if t.status == "completed"]
    
    if not completed_tasks:
        text = f"{title} (выполненные):\nНет выполненных задач."
    else:
        text = f"{title} (выполненные):\n" + "\n".join(f"#{t.task_id} {t.description}" for t in completed_tasks)

    keyboard = InlineKeyboardBuilder()
    for task in completed_tasks:
        keyboard.row(InlineKeyboardButton(text=f"Отменить #{task.task_id}", callback_data=f"undo_{task.task_id}"))
    keyboard.row(InlineKeyboardButton(text="Невыполненные задачи", callback_data="hide_completed"))
    keyboard.row(InlineKeyboardButton(text="Назад", callback_data="tasks"))
    
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await state.update_data(show_completed=True)
    await callback.answer()

# Скрыть выполненные задачи
@router.callback_query(TaskState.viewing_tasks, F.data == "hide_completed")
async def hide_completed_tasks(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    tasks = data["tasks"]
    title = data["title"]
    
    incomplete_tasks = [t for t in tasks if t.status != "completed"]
    
    if not incomplete_tasks:
        text = f"{title} (невыполненные):\nНет невыполненных задач."
    else:
        text = f"{title} (невыполненные):\n" + "\n".join(f"#{t.task_id} {t.description}" for t in incomplete_tasks)

    keyboard = InlineKeyboardBuilder()
    for task in incomplete_tasks:
        keyboard.row(InlineKeyboardButton(text=f"Выполнить #{task.task_id}", callback_data=f"complete_{task.task_id}"))
    keyboard.row(InlineKeyboardButton(text="Показать выполненные", callback_data="show_completed"))
    keyboard.row(InlineKeyboardButton(text="Назад", callback_data="tasks"))
    
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await state.update_data(show_completed=False)
    await callback.answer()

# Отметить задачу выполненной
@router.callback_query(TaskState.viewing_tasks, F.data.startswith("complete_"))
async def complete_task(callback: CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split("_")[1])
    user_id = str(callback.from_user.id)
    await add_task_completion(task_id, user_id, "completed", datetime.now())
    await update_task_status(task_id, "completed")  # Синхронизация с tasks_table
    
    # Обновляем список задач
    await hide_completed_tasks(callback, state)
    await callback.answer(f"Задача #{task_id} отмечена как выполненная.")

# Отменить выполнение задачи
@router.callback_query(TaskState.viewing_tasks, F.data.startswith("undo_"))
async def undo_task(callback: CallbackQuery, state: FSMContext):
    task_id = int(callback.data.split("_")[1])
    user_id = str(callback.from_user.id)
    await add_task_completion(task_id, user_id, "accepted", None)
    await update_task_status(task_id, "accepted")  # Синхронизация с tasks_table
    
    # Обновляем список задач
    await show_completed_tasks(callback, state)
    await callback.answer(f"Статус задачи #{task_id} изменён на 'принято'.")

# Возврат в главное меню
@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    role_user = await get_user_role(user_id)
    if not role_user:
        await callback.message.edit_text("Вы не авторизованы. Введите /start для входа.")
        await callback.answer()
        return
    
    role = await get_role_by_id(role_user.role_id)
    await callback.message.edit_text(
        f"Добро пожаловать, {role.role_full_name}! Вот ваше меню:",
        reply_markup=get_main_menu(role.role_group)
    )
    await state.clear()
    await callback.answer()

# Динамическое меню
@router.callback_query(lambda c: c.data in ["voz", "menu"])
async def process_dynamic_menu(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    role_user = await get_user_role(user_id)
    if not role_user:
        await callback.message.edit_text("Вы не авторизованы. Введите /start для входа.")
        await callback.answer()
        return
    
    role = await get_role_by_id(role_user.role_id)
    button = await get_button_by_data(role.role_group or "menu")
    
    if not button:
        await callback.message.edit_text("Динамическое меню для вашей роли не настроено.")
        await callback.answer()
        return
    
    await show_dynamic_menu(callback, button)

@router.callback_query(F.data.startswith("btn_"))
async def process_dynamic_button(callback: CallbackQuery):
    button_data = callback.data.split("_")[1]
    button = await get_button_by_data(button_data)
    
    if not button:
        await callback.message.edit_text("Кнопка не найдена.")
        await callback.answer()
        return
    
    if button.type == "menu":
        await show_dynamic_menu(callback, button)
    elif button.type == "text":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data=f"btn_{button.parentdataorcommand}")]
        ])
        await callback.message.edit_text(button.text, reply_markup=keyboard)
        await callback.answer()
    elif button.type == "url":
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=button.name, url=button.text)],
            [InlineKeyboardButton(text="Назад", callback_data=f"btn_{button.parentdataorcommand}")]
        ])
        await callback.message.edit_text("Перейдите по ссылке:", reply_markup=keyboard)
        await callback.answer()

async def show_dynamic_menu(callback: CallbackQuery, button):
    keyboard = InlineKeyboardBuilder()
    for i in range(1, 16):
        submdata = getattr(button, f"submdata{i}", None)
        if submdata and submdata != "0":
            sub_button = await get_button_by_data(submdata)
            if sub_button:
                if sub_button.type == "url":
                    keyboard.row(InlineKeyboardButton(text=sub_button.name, url=sub_button.text))
                else:
                    keyboard.row(InlineKeyboardButton(text=sub_button.name, callback_data=f"btn_{submdata}"))
    
    keyboard.row(InlineKeyboardButton(text="Назад", callback_data="back_to_main"))
    await callback.message.edit_text(button.text or "Динамическое меню", reply_markup=keyboard.as_markup())
    await callback.answer()

# Смена роли
@router.callback_query(F.data == "change_role")
async def process_change_role(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    role_user = await get_user_role(user_id)
    if not role_user:
        await callback.message.edit_text("Вы не авторизованы. Введите /start для входа.")
        await callback.answer()
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data="confirm_change_role")],
        [InlineKeyboardButton(text="Нет", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(
        "Вы действительно хотите покинуть свою роль? Вы не сможете вернуться без повторного ввода пароля.",
        reply_markup=keyboard
    )
    await state.set_state(ChangeRoleState.confirming)
    await callback.answer()

@router.callback_query(F.data == "confirm_change_role", ChangeRoleState.confirming)
async def confirm_change_role(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    await unbind_user_from_role(user_id)
    await callback.message.edit_text("Вы покинули свою роль. Введите /start для новой авторизации.")
    await state.clear()
    await callback.answer()