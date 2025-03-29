from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from utils.database import buttons_table, async_session
from sqlalchemy.future import select
from config import settings
from aiogram.utils.keyboard import InlineKeyboardBuilder
import os

add_button_router = Router()

# Стейты для создания кнопки
class DynamicMenuStates(StatesGroup):
    ADD_BUTTON_DATA = State()
    ADD_BUTTON_COMMAND = State()
    ADD_BUTTON_PARENT = State()
    ADD_BUTTON_NAME = State()
    ADD_BUTTON_TYPE = State()
    ADD_BUTTON_TEXT = State()
    ADD_BUTTON_IMAGE = State()
    ADD_BUTTON_SUBMENUS = State()

# Обработчик кнопки "Добавить кнопку"
@add_button_router.callback_query(F.data == "add_button")
async def start_add_button(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer(
        "Введите уникальное кодовое имя кнопки (Data):\n"
        "Уникальное имя должно состоять только из латинских букв и/или цифр без пробелов."
    )
    await state.set_state(DynamicMenuStates.ADD_BUTTON_DATA)
    await callback.answer()

# Шаг 1: Ввод уникального кодового имени (Data)
@add_button_router.message(DynamicMenuStates.ADD_BUTTON_DATA)
async def process_data(message: Message, state: FSMContext):
    button_data = message.text.strip()
    
    # Проверяем, не существует ли уже такая запись в базе данных
    async with async_session() as session:
        query = select(buttons_table).where(buttons_table.c.data == button_data)
        result = await session.execute(query)
        if result.fetchone():
            await message.answer("Такое имя уже существует. Введите другое:")
            return

    # Сохраняем данные в состояние пользователя
    await state.update_data({"data": button_data})  # Исправленная строка
    await message.answer(
        "Как будет вызываться кнопка?",
        reply_markup=InlineKeyboardBuilder().row(
            InlineKeyboardButton(text="По команде", callback_data="command"),
            InlineKeyboardButton(text="По нажатию в другом меню", callback_data="parent")
        ).as_markup()
    )
    await state.set_state(DynamicMenuStates.ADD_BUTTON_COMMAND)

# Шаг 2: Выбор способа вызова кнопки
@add_button_router.callback_query(DynamicMenuStates.ADD_BUTTON_COMMAND, F.data.in_(["command", "parent"]))
async def process_command(callback: CallbackQuery, state: FSMContext):
    command_type = 1 if callback.data == "command" else 0
    await state.update_data(command=command_type)

    if command_type == 1:  # Вызов по команде
        await callback.message.edit_text("Введите команду для вызова кнопки (без '/'): ")
        await state.set_state(DynamicMenuStates.ADD_BUTTON_PARENT)
    else:  # Вызов через родительскую кнопку
        await callback.message.edit_text("Введите data родительской кнопки:")
        await state.set_state(DynamicMenuStates.ADD_BUTTON_PARENT)

    await callback.answer()

# Шаг 3: Ввод команды или родительской кнопки
@add_button_router.message(DynamicMenuStates.ADD_BUTTON_PARENT)
async def process_parent(message: Message, state: FSMContext):
    parent_data = message.text.strip()
    async with async_session() as session:
        query = select(buttons_table).where(buttons_table.c.data == parent_data)
        result = await session.execute(query)
        if not result.fetchone() and (await state.get_data()).get("command") == 0:
            await message.answer("Родительская кнопка не найдена. Попробуйте еще раз:")
            return

    await state.update_data(parentdataorcommand=parent_data)

    if (await state.get_data()).get("command") == 1:  # Команда
        await state.update_data(name="0")  # Для команд имя всегда "0"
        await message.answer("Выберите тип кнопки:", reply_markup=get_type_keyboard(is_command=True))
        await state.set_state(DynamicMenuStates.ADD_BUTTON_TYPE)
    else:  # Родительская кнопка
        await message.answer("Введите название кнопки:")
        await state.set_state(DynamicMenuStates.ADD_BUTTON_NAME)

# Шаг 4: Ввод названия кнопки
@add_button_router.message(DynamicMenuStates.ADD_BUTTON_NAME)
async def process_name(message: Message, state: FSMContext):
    button_name = message.text.strip()
    await state.update_data(name=button_name)
    await message.answer("Выберите тип кнопки:", reply_markup=get_type_keyboard(is_command=False))
    await state.set_state(DynamicMenuStates.ADD_BUTTON_TYPE)

# Шаг 5: Выбор типа кнопки
@add_button_router.callback_query(DynamicMenuStates.ADD_BUTTON_TYPE, F.data.in_(["menu", "text", "textimage", "url"]))
async def process_type(callback: CallbackQuery, state: FSMContext):
    button_type = callback.data
    await state.update_data(type=button_type)

    if button_type == "menu":
        await callback.message.edit_text("Введите текст, который будет отображаться в меню:")
    elif button_type in ["text", "textimage"]:
        await callback.message.edit_text("Введите текстовое сообщение для кнопки:")
    elif button_type == "url":
        await callback.message.edit_text("Введите URL-ссылку для кнопки:")

    await state.set_state(DynamicMenuStates.ADD_BUTTON_TEXT)
    await callback.answer()

# Шаг 6: Заполнение дополнительных параметров
@add_button_router.message(DynamicMenuStates.ADD_BUTTON_TEXT)
async def process_text(message: Message, state: FSMContext):
    button_text = message.text.strip()
    await state.update_data(text=button_text)

    button_type = (await state.get_data()).get("type")
    if button_type == "menu":
        await message.answer("Введите Data первой подкнопки (или 'Стоп' для завершения):")
        await state.set_state(DynamicMenuStates.ADD_BUTTON_SUBMENUS)
    elif button_type in ["text", "url"]:
        await save_button(message, state)
    elif button_type == "textimage":
        await message.answer("Отправьте изображение, которое будет отображаться:")
        await state.set_state(DynamicMenuStates.ADD_BUTTON_IMAGE)  # Переход к следующему состоянию

# Обработка изображения для кнопки типа textimage
@add_button_router.message(DynamicMenuStates.ADD_BUTTON_IMAGE, F.photo)
async def process_image(message: Message, state: FSMContext):
    from main import bot  # Import here
    # Сохраняем изображение
    file_id = message.photo[-1].file_id
    file = await bot.get_file(file_id)
    file_path = file.file_path

    # Получаем data для названия файла
    state_data = await state.get_data()
    data = state_data["data"]

    # Создаем папку img, если её нет
    if not os.path.exists("img"):
        os.makedirs("img")

    # Сохраняем файл
    destination = f"img/{data}.jpg"
    await bot.download_file(file_path, destination)

    # Сохраняем кнопку
    await save_button(message, state)

# Шаг 7: Создание подменю
@add_button_router.message(DynamicMenuStates.ADD_BUTTON_SUBMENUS)
async def process_submenus(message: Message, state: FSMContext):
    subm_data = message.text.strip().lower()
    if subm_data == "стоп":
        await save_button(message, state)
        return

    state_data = await state.get_data()
    submenus = state_data.get("submenus", [])
    if len(submenus) >= 15:
        await message.answer("Максимальное количество подкнопок достигнуто.")
        await save_button(message, state)
        return

    submenus.append(subm_data)
    await state.update_data(submenus=submenus)
    await message.answer(f"Подкнопка {subm_data} добавлена. Введите следующую (или 'Стоп' для завершения):")

# Сохранение кнопки в базу данных
async def save_button(message: Message, state: FSMContext):
    state_data = await state.get_data()

    async with async_session() as session:
        # Вставляем основные данные кнопки
        query = buttons_table.insert().values(
            data=state_data["data"],
            command=state_data["command"],
            parentdataorcommand=state_data["parentdataorcommand"],
            name=state_data.get("name", ""),
            type=state_data["type"],
            text=state_data.get("text", "")
        )
        await session.execute(query)

        # Обновляем поля подменю
        if state_data.get("submenus"):
            for i, subm in enumerate(state_data["submenus"], start=1):
                update_query = (
                    buttons_table.update().
                    where(buttons_table.c.data == state_data["data"]).
                    values(**{f"submdata{i}": subm})
                )
                await session.execute(update_query)

        await session.commit()

    # Формируем уведомление об успешном добавлении
    command = "По команде" if state_data["command"] == 1 else "По нажатию в другом меню"
    response = f"Кнопка успешно добавлена!\nТип вызова: {command}\n"

    if state_data["command"] == 1:
        response += f"Команда: /{state_data['parentdataorcommand']}\n"
    else:
        response += f"Родительская кнопка: {state_data['parentdataorcommand']}\nНазвание кнопки: {state_data['name']}\n"

    response += f"Тип кнопки: {state_data['type'].capitalize()}\n"

    if state_data["type"] == "menu":
        submenus = state_data.get("submenus", [])
        response += "Подменю:\n"
        for i, subm in enumerate(submenus, start=1):
            response += f"  {i}. Data дочерней кнопки: {subm}\n"
    elif state_data["type"] in ["text", "textimage"]:
        response += f"Текст сообщения: {state_data['text']}\n"
        if state_data["type"] == "textimage":
            response += f"Изображение сохранено как: {state_data['data']}.jpg\n"
    elif state_data["type"] == "url":
        response += f"Ссылка: {state_data['text']}\n"

    await message.answer(response)
    await state.clear()
    
    # Перенаправляем администратора обратно в динамическое меню
    from bot.adminpanel import DYNAMIC_MENU  # Import here to avoid circular imports
    await message.answer(
        "Вы можете продолжить настройку динамического меню:",
        reply_markup=DYNAMIC_MENU
    )



# Функция для создания клавиатуры выбора типа кнопки
def get_type_keyboard(is_command: bool):
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="Меню", callback_data="menu"),
        InlineKeyboardButton(text="Текст", callback_data="text"),
        InlineKeyboardButton(text="Текст + Картинка", callback_data="textimage")
    )
    if not is_command:
        keyboard.row(
            InlineKeyboardButton(text="URL (ссылка)", callback_data="url")
        )
    return keyboard.as_markup()