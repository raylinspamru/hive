# bot/edit_button.py

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from utils.database import buttons_table, async_session
from sqlalchemy.future import select
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

logging.basicConfig(level=logging.INFO)

edit_button_router = Router()

class EditButtonStates(StatesGroup):
    SELECT_BUTTON = State()
    SELECT_PARAMETER = State()
    EDIT_DATA = State()
    EDIT_COMMAND = State()
    EDIT_PARENT = State()
    EDIT_NAME = State()
    EDIT_TYPE = State()
    EDIT_TEXT = State()
    EDIT_IMAGE = State()
    EDIT_SUBMENU = State()
    ADD_SUBBUTTON = State()
    DELETE_SUBBUTTON = State()
    CONFIRM_CHANGES = State()

@edit_button_router.callback_query(F.data == "back_to_edit_params")
async def back_to_edit_params(callback: CallbackQuery, state: FSMContext):
    await show_current_parameters(callback.message, state)
    await state.set_state(EditButtonStates.SELECT_PARAMETER)
    await callback.answer()

async def confirm_changes(message: Message, state: FSMContext):
    logging.info("Entering confirm_changes")
    data = await state.get_data()
    button = data['original_button']
    pending_updates = data.get('pending_updates', {})
    
    updated_button = dict(button)
    updated_button.update(pending_updates)
    
    text = (
        "Вы уверены, что хотите сохранить изменения?\n\n"
        f"Новые параметры:\n"
        f"Data: {updated_button['data']}\n"
        f"Способ вызова: {'По команде' if updated_button['command'] == 1 else 'По нажатию'}\n"
        f"Родительская кнопка/Команда: {updated_button['parentdataorcommand']}\n"
        f"Название: {updated_button['name']}\n"
        f"Тип: {updated_button['type']}\n"
        f"Текст/Ссылка: {updated_button['text']}\n"
    )
    
    if updated_button['type'] == 'menu':
        submenus = [updated_button.get(f"submdata{i}") for i in range(1, 16) if updated_button.get(f"submdata{i}", None)]
        text += "Подменю:\n" + "\n".join([f"{i+1}. {sub}" for i, sub in enumerate(submenus)])
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text="Сохранить", callback_data="save_changes"),
        InlineKeyboardButton(text="Отменить", callback_data="cancel_changes")
    )
    logging.info("Sending confirmation message")
    await message.answer(text, reply_markup=keyboard.as_markup())
    await state.set_state(EditButtonStates.CONFIRM_CHANGES)
    logging.info("Confirmation message sent, state set to CONFIRM_CHANGES")

@edit_button_router.callback_query(F.data == "save_changes")
async def save_changes(callback: CallbackQuery, state: FSMContext):
    from main import bot
    chat_id = callback.message.chat.id
    logging.info(f"Starting save_changes for chat {chat_id}, current state: {await state.get_state()}")
    try:
        logging.info(f"Attempting to delete message in chat {chat_id}")
        await callback.message.delete()
        logging.info("Message deleted successfully")
        await state.update_data(pending_updates={})  # Очищаем временные изменения
        logging.info(f"Sending 'Changes saved' to chat {chat_id}")
        await bot.send_message(chat_id, "Изменения успешно сохранены!")
        
        # Получаем актуальные данные из базы после сохранения
        logging.info("Fetching updated button data from database")
        data = await state.get_data()
        button_data = data['button_data']
        button_row = await get_button_by_data(button_data)  # Получаем актуальные данные
        button = button_row._mapping if button_row else data['original_button']  # Используем базу или старые данные
        await state.update_data(original_button=button)  # Обновляем original_button в состоянии
        
        # Показываем актуальные параметры
        text = (
            f"Текущие параметры кнопки:\n"
            f"Data: {button['data']}\n"
            f"Способ вызова: {'По команде' if button['command'] == 1 else 'По нажатию в другом меню'}\n"
            f"Родительская кнопка/Команда: {button['parentdataorcommand']}\n"
            f"Название: {button['name']}\n"
            f"Тип: {button['type']}\n"
            f"Текст/Ссылка: {button['text']}\n"
        )
        if button['type'] == 'menu':
            submenus = [button.get(f"submdata{i}") for i in range(1, 16) if button.get(f"submdata{i}", None)]
            text += "Подменю:\n" + "\n".join([f"{i+1}. {sub}" for i, sub in enumerate(submenus)])
        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text="Data(уникальное имя)", callback_data="edit_data"))
        keyboard.row(InlineKeyboardButton(text="Способ вызова", callback_data="edit_command"))
        keyboard.row(InlineKeyboardButton(text="Родительская кнопка/Команда", callback_data="edit_parent"))
        keyboard.row(
            InlineKeyboardButton(text="Название", callback_data="edit_name"),
            InlineKeyboardButton(text="Тип", callback_data="edit_type")
        )
        keyboard.row(InlineKeyboardButton(text="Текст/Ссылка", callback_data="edit_text"))
        if button['type'] == 'textimage':
            keyboard.row(InlineKeyboardButton(text="Изображение", callback_data="edit_image"))
        if button['type'] == 'menu':
            keyboard.row(InlineKeyboardButton(text="Подменю", callback_data="edit_submenu"))
        keyboard.row(InlineKeyboardButton(text="Назад", callback_data="back_to_dynamic_menu"))
        logging.info(f"Sending updated parameters to chat {chat_id}")
        await bot.send_message(chat_id, text, reply_markup=keyboard.as_markup())
        logging.info("Save_changes completed successfully")
        await callback.answer("Изменения сохранены успешно")
    except Exception as e:
        logging.error(f"Error in save_changes: {e}")
        await callback.answer(f"Ошибка при сохранении: {e}", show_alert=True)
    

@edit_button_router.callback_query(F.data == "cancel_changes")
async def cancel_changes(callback: CallbackQuery, state: FSMContext):
    from main import bot
    chat_id = callback.message.chat.id
    logging.info(f"Starting cancel_changes for chat {chat_id}, current state: {await state.get_state()}")
    try:
        logging.info(f"Attempting to delete message in chat {chat_id}")
        await callback.message.delete()
        logging.info("Message deleted successfully")
        
        # Получаем данные из состояния
        data = await state.get_data()
        button_data = data['button_data']
        original_button = data['original_button']  # Исходное состояние кнопки
        pending_updates = data.get('pending_updates', {})
        
        # Откатываем изменения в базе, возвращая исходное состояние
        if pending_updates:
            async with async_session() as session:
                # Формируем запрос на обновление, возвращая исходные данные
                query = (
                    buttons_table.update().
                    where(buttons_table.c.data == button_data).
                    values(**original_button)  # Восстанавливаем исходное состояние
                )
                await session.execute(query)
                await session.commit()
                logging.info(f"Changes rolled back in database for button {button_data}")
        
        await state.update_data(pending_updates={})
        logging.info(f"Sending 'Changes cancelled' to chat {chat_id}")
        await bot.send_message(chat_id, "Изменения отменены.")
        
        # Показываем текущее состояние кнопки (должно быть без a12)
        button = original_button  # Используем исходное состояние
        text = (
            f"Текущие параметры кнопки:\n"
            f"Data: {button['data']}\n"
            f"Способ вызова: {'По команде' if button['command'] == 1 else 'По нажатию в другом меню'}\n"
            f"Родительская кнопка/Команда: {button['parentdataorcommand']}\n"
            f"Название: {button['name']}\n"
            f"Тип: {button['type']}\n"
            f"Текст/Ссылка: {button['text']}\n"
        )
        if button['type'] == 'menu':
            submenus = [button.get(f"submdata{i}") for i in range(1, 16) if button.get(f"submdata{i}", None)]
            text += "Подменю:\n" + "\n".join([f"{i+1}. {sub}" for i, sub in enumerate(submenus)])
        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text="Data(уникальное имя)", callback_data="edit_data"))
        keyboard.row(InlineKeyboardButton(text="Способ вызова", callback_data="edit_command"))
        keyboard.row(InlineKeyboardButton(text="Родительская кнопка/Команда", callback_data="edit_parent"))
        keyboard.row(
            InlineKeyboardButton(text="Название", callback_data="edit_name"),
            InlineKeyboardButton(text="Тип", callback_data="edit_type")
        )
        keyboard.row(InlineKeyboardButton(text="Текст/Ссылка", callback_data="edit_text"))
        if button['type'] == 'textimage':
            keyboard.row(InlineKeyboardButton(text="Изображение", callback_data="edit_image"))
        if button['type'] == 'menu':
            keyboard.row(InlineKeyboardButton(text="Подменю", callback_data="edit_submenu"))
        keyboard.row(InlineKeyboardButton(text="Назад", callback_data="back_to_dynamic_menu"))
        logging.info(f"Sending current parameters to chat {chat_id}")
        await bot.send_message(chat_id, text, reply_markup=keyboard.as_markup())
        logging.info("Cancel_changes completed successfully")
        await callback.answer("Изменения отменены успешно")
    except Exception as e:
        logging.error(f"Error in cancel_changes: {e}")
        await callback.answer(f"Ошибка при отмене: {e}", show_alert=True)

@edit_button_router.callback_query(F.data == "edit_button")
async def start_edit_button(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.message.answer(
        "Редактировать можно только существующие кнопки. "
        "Введите уникальное кодовое имя кнопки (Data), которую хотите отредактировать:\n"
        "Чтобы вернуться назад, нажмите кнопку 'Назад'.",
        reply_markup=InlineKeyboardBuilder().row(
            InlineKeyboardButton(text="Назад", callback_data="back_to_dynamic_menu")
        ).as_markup()
    )
    await state.set_state(EditButtonStates.SELECT_BUTTON)

@edit_button_router.callback_query(F.data == "back_to_dynamic_menu")
async def back_to_dynamic_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "Вы можете управлять динамическим меню:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Просмотреть кнопки", callback_data="view_buttons")],
            [InlineKeyboardButton(text="Добавить кнопку", callback_data="add_button")],
            [InlineKeyboardButton(text="Редактировать кнопку", callback_data="edit_button")],
            [InlineKeyboardButton(text="Удалить кнопку", callback_data="delete_button")],
            [InlineKeyboardButton(text="Назад", callback_data="back_to_admin_menu")]
        ])
    )
    await callback.answer()

@edit_button_router.message(EditButtonStates.SELECT_BUTTON, ~F.text.startswith('/'))
async def select_button(message: Message, state: FSMContext):
    button_data = message.text.strip()
    button = await get_button_by_data(button_data)
    
    if not button:
        await message.answer("Кнопка с таким именем не найдена. Попробуйте еще раз.")
        return
    
    await state.update_data(button_data=button_data, original_button=button._mapping)
    await show_current_parameters(message, state)
    await state.set_state(EditButtonStates.SELECT_PARAMETER)

@edit_button_router.message(EditButtonStates.SELECT_BUTTON, F.text.startswith('/'))
async def handle_commands_in_select_button(message: Message, state: FSMContext):
    await message.answer(
        "Пожалуйста, введите уникальное кодовое имя кнопки (Data) без использования команд (например, без '/').\n"
        "Если вы хотите выйти, используйте кнопку 'Назад'."
    )

async def show_current_parameters(message: Message, state: FSMContext):
    data = await state.get_data()
    button = data['original_button']
    
    text = (
        f"Текущие параметры кнопки:\n"
        f"Data: {button['data']}\n"
        f"Способ вызова: {'По команде' if button['command'] == 1 else 'По нажатию в другом меню'}\n"
        f"Родительская кнопка/Команда: {button['parentdataorcommand']}\n"
        f"Название: {button['name']}\n"
        f"Тип: {button['type']}\n"
        f"Текст/Ссылка: {button['text']}\n"
    )
    
    if button['type'] == 'menu':
        submenus = [getattr(button, f"submdata{i}") for i in range(1, 16) if getattr(button, f"submdata{i}", None)]
        text += "Подменю:\n" + "\n".join([f"{i+1}. {sub}" for i, sub in enumerate(submenus)])
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="Data(уникальное имя)", callback_data="edit_data"))
    keyboard.row(InlineKeyboardButton(text="Способ вызова", callback_data="edit_command"))
    keyboard.row(InlineKeyboardButton(text="Родительская кнопка/Команда", callback_data="edit_parent"))
    keyboard.row(
        InlineKeyboardButton(text="Название", callback_data="edit_name"),
        InlineKeyboardButton(text="Тип", callback_data="edit_type")
    )
    keyboard.row(InlineKeyboardButton(text="Текст/Ссылка", callback_data="edit_text"))
    if button['type'] == 'textimage':
        keyboard.row(InlineKeyboardButton(text="Изображение", callback_data="edit_image"))
    if button['type'] == 'menu':
        keyboard.row(InlineKeyboardButton(text="Подменю", callback_data="edit_submenu"))
    keyboard.row(InlineKeyboardButton(text="Назад", callback_data="back_to_dynamic_menu"))
    
    await message.answer(text, reply_markup=keyboard.as_markup())

@edit_button_router.callback_query(F.data == "back_to_edit_params")
async def back_to_edit_params(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await state.clear()
    await show_current_parameters(callback.message, state)
    await state.set_state(EditButtonStates.SELECT_PARAMETER)
    await callback.answer()

@edit_button_router.callback_query(EditButtonStates.SELECT_PARAMETER, F.data.startswith("edit_"))
async def edit_parameter(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    parameter = callback.data.split("_")[1]

    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="Отмена", callback_data="back_to_edit_params"))

    if parameter == "data":
        await callback.message.answer(
            "Уникальное имя должно состоять только из латинских букв и/или цифр без пробелов.\n"
            "Введите новое уникальное кодовое имя кнопки (Data) или вернитесь назад.",
            reply_markup=keyboard.as_markup()
        )
        await state.set_state(EditButtonStates.EDIT_DATA)
    elif parameter == "command":
        await callback.message.answer(
            "Выберите новый способ вызова:",
            reply_markup=InlineKeyboardBuilder().row(
                InlineKeyboardButton(text="По команде", callback_data="command_1"),
                InlineKeyboardButton(text="По нажатию в другом меню", callback_data="command_0"),
                InlineKeyboardButton(text="Отмена", callback_data="back_to_edit_params")
            ).as_markup()
        )
        await state.set_state(EditButtonStates.EDIT_COMMAND)
    elif parameter == "parent":
        await callback.message.answer(
            "Введите новое значение родительской кнопки/команды или вернитесь назад.",
            reply_markup=keyboard.as_markup()
        )
        await state.set_state(EditButtonStates.EDIT_PARENT)
    elif parameter == "name":
        await callback.message.answer(
            "Введите новое название кнопки или вернитесь назад.",
            reply_markup=keyboard.as_markup()
        )
        await state.set_state(EditButtonStates.EDIT_NAME)
    elif parameter == "type":
        data = await state.get_data()
        command = data['original_button']['command']
        
        type_keyboard = InlineKeyboardBuilder()
        if command == 0:
            type_keyboard.row(InlineKeyboardButton(text="Меню", callback_data="type_menu"))
            type_keyboard.row(InlineKeyboardButton(text="Текст", callback_data="type_text"))
            type_keyboard.row(InlineKeyboardButton(text="Текст + Картинка", callback_data="type_textimage"))
            type_keyboard.row(InlineKeyboardButton(text="URL (ссылка)", callback_data="type_url"))
        else:
            type_keyboard.row(InlineKeyboardButton(text="Меню", callback_data="type_menu"))
            type_keyboard.row(InlineKeyboardButton(text="Текст", callback_data="type_text"))
            type_keyboard.row(InlineKeyboardButton(text="Текст + Картинка", callback_data="type_textimage"))
        
        type_keyboard.row(InlineKeyboardButton(text="Отмена", callback_data="back_to_edit_params"))
        
        await callback.message.answer(
            "Выберите новый тип кнопки или вернитесь назад.",
            reply_markup=type_keyboard.as_markup()
        )
        await state.set_state(EditButtonStates.EDIT_TYPE)
    elif parameter == "text":
        await callback.message.answer(
            "Введите новый текст / новую ссылку или вернитесь назад.",
            reply_markup=keyboard.as_markup()
        )
        await state.set_state(EditButtonStates.EDIT_TEXT)
    elif parameter == "image":
        await callback.message.answer(
            "Отправьте новое изображение или вернитесь назад.",
            reply_markup=keyboard.as_markup()
        )
        await state.set_state(EditButtonStates.EDIT_IMAGE)
    elif parameter == "submenu":
        await edit_submenu(callback, state)
    
    await callback.answer()

@edit_button_router.message(EditButtonStates.EDIT_DATA)
async def process_edit_data(message: Message, state: FSMContext):
    new_data = message.text.strip()
    updates = {"data": new_data}
    await update_button(state, updates)
    await state.update_data(pending_updates=updates)
    await message.answer(f"Data изменено на {new_data}.")
    await confirm_changes(message, state)
    await state.set_state(EditButtonStates.SELECT_PARAMETER)

@edit_button_router.callback_query(EditButtonStates.EDIT_COMMAND, F.data.startswith("command_"))
async def process_edit_command(callback: CallbackQuery, state: FSMContext):
    command = int(callback.data.split("_")[1])
    updates = {"command": command}
    await update_button(state, updates)
    await state.update_data(pending_updates=updates)
    await callback.message.answer(f"Способ вызова изменен на {'По команде' if command == 1 else 'По нажатию'}.")
    await confirm_changes(callback.message, state)
    await state.set_state(EditButtonStates.SELECT_PARAMETER)
    await callback.answer()

@edit_button_router.message(EditButtonStates.EDIT_PARENT)
async def process_edit_parent(message: Message, state: FSMContext):
    parent = message.text.strip()
    updates = {"parentdataorcommand": parent}
    await update_button(state, updates)
    await state.update_data(pending_updates=updates)
    await message.answer(f"Родительская кнопка/команда изменена на {parent}.")
    await confirm_changes(message, state)
    await state.set_state(EditButtonStates.SELECT_PARAMETER)

@edit_button_router.message(EditButtonStates.EDIT_NAME)
async def process_edit_name(message: Message, state: FSMContext):
    name = message.text.strip()
    updates = {"name": name}
    await update_button(state, updates)
    await state.update_data(pending_updates=updates)
    await message.answer(f"Название изменено на {name}.")
    await confirm_changes(message, state)
    await state.set_state(EditButtonStates.SELECT_PARAMETER)

@edit_button_router.callback_query(EditButtonStates.EDIT_TYPE, F.data.startswith("type_"))
async def process_edit_type(callback: CallbackQuery, state: FSMContext):
    button_type = callback.data.split("_")[1]
    updates = {"type": button_type}

    if button_type != "menu":
        for i in range(1, 16):
            updates[f"submdata{i}"] = "0"

    await update_button(state, updates)
    await state.update_data(pending_updates=updates)
    await callback.message.answer(f"Тип изменен на {button_type}.")
    await confirm_changes(callback.message, state)
    await state.set_state(EditButtonStates.SELECT_PARAMETER)
    await callback.answer()

@edit_button_router.message(EditButtonStates.EDIT_TEXT)
async def process_edit_text(message: Message, state: FSMContext):
    text = message.text.strip()
    updates = {"text": text}
    await update_button(state, updates)
    await state.update_data(pending_updates=updates)
    await message.answer(f"Текст/ссылка изменены на {text}.")
    await confirm_changes(message, state)
    await state.set_state(EditButtonStates.SELECT_PARAMETER)

@edit_button_router.message(EditButtonStates.EDIT_IMAGE)
async def process_edit_image(message: Message, state: FSMContext):
    if not message.photo:
        await message.answer("Пожалуйста, отправьте изображение.")
        return

    from main import bot
    try:
        file_id = message.photo[-1].file_id
        file = await bot.get_file(file_id)
        file_path = file.file_path
        data = await state.get_data()
        destination = f"img/{data['button_data']}.jpg"
        await bot.download_file(file_path, destination)
        updates = {}
        await state.update_data(pending_updates=updates)
        await message.answer("Изображение обновлено.")
        await confirm_changes(message, state)
        await state.set_state(EditButtonStates.SELECT_PARAMETER)
    except Exception as e:
        await message.answer(f"Произошла ошибка: {e}")

@edit_button_router.callback_query(EditButtonStates.SELECT_PARAMETER, F.data == "edit_submenu")
async def edit_submenu(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    button = data['original_button']
    
    submenus = [getattr(button, f"submdata{i}") for i in range(1, 16) if getattr(button, f"submdata{i}", None)]
    text = "Выберите подкнопку для редактирования или выполните действие:\n" if submenus else "Подменю пусто. Добавьте подкнопку:\n"
    
    keyboard = InlineKeyboardBuilder()
    for i, sub in enumerate(submenus, start=1):
        keyboard.row(InlineKeyboardButton(text=f"{i}. {sub}", callback_data=f"edit_sub:{sub}"))
    
    keyboard.row(InlineKeyboardButton(text="Добавить подкнопку", callback_data="add_subbutton"))
    if submenus:
        keyboard.row(InlineKeyboardButton(text="Удалить подкнопку", callback_data="delete_subbutton"))
    keyboard.row(InlineKeyboardButton(text="Назад", callback_data="back_to_edit_params"))
    
    await callback.message.answer(text, reply_markup=keyboard.as_markup())
    await callback.answer()

@edit_button_router.callback_query(F.data.startswith("edit_sub:"))
async def edit_subbutton(callback: CallbackQuery, state: FSMContext):
    subbutton_data = callback.data.split(":")[1]
    await state.update_data(selected_subbutton=subbutton_data)
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="Назад", callback_data="edit_submenu"))
    
    await callback.message.edit_text(
        f"Вы выбрали подкнопку: {subbutton_data}\nВведите новое значение Data для этой подкнопки:",
        reply_markup=keyboard.as_markup()
    )
    await state.set_state(EditButtonStates.EDIT_SUBMENU)
    await callback.answer()

@edit_button_router.message(EditButtonStates.EDIT_SUBMENU)
async def process_edit_subbutton(message: Message, state: FSMContext):
    new_subbutton_data = message.text.strip()
    data = await state.get_data()
    button = data['original_button']
    old_subbutton_data = data['selected_subbutton']
    
    for i in range(1, 16):
        if getattr(button, f"submdata{i}", None) == old_subbutton_data:
            updates = {f"submdata{i}": new_subbutton_data}
            await update_button(state, updates)
            await state.update_data(pending_updates=updates)
            break
    
    await message.answer(f"Подкнопка изменена с {old_subbutton_data} на {new_subbutton_data}.")
    await confirm_changes(message, state)
    await state.set_state(EditButtonStates.SELECT_PARAMETER)

@edit_button_router.callback_query(F.data == "add_subbutton")
async def add_subbutton(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    button = data['original_button']
    
    free_slots = [i for i in range(1, 16) if not getattr(button, f"submdata{i}", None)]
    if not free_slots:
        await callback.message.edit_text("Максимальное количество подкнопок достигнуто.")
        await callback.answer()
        return
    
    await state.update_data(free_slots=free_slots)
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="Назад", callback_data="edit_submenu"))
    
    await callback.message.edit_text(
        "Введите Data новой подкнопки:",
        reply_markup=keyboard.as_markup()
    )
    await state.set_state(EditButtonStates.ADD_SUBBUTTON)
    await callback.answer()

@edit_button_router.message(EditButtonStates.ADD_SUBBUTTON)
async def process_add_subbutton(message: Message, state: FSMContext):
    new_subbutton_data = message.text.strip()
    data = await state.get_data()
    free_slots = data['free_slots']
    
    slot = free_slots[0]
    updates = {f"submdata{slot}": new_subbutton_data}
    await update_button(state, updates)
    await state.update_data(pending_updates=updates)
    
    await message.answer(f"Подкнопка {new_subbutton_data} добавлена в позицию {slot}.")
    await confirm_changes(message, state)
    await state.set_state(EditButtonStates.SELECT_PARAMETER)

@edit_button_router.callback_query(F.data == "delete_subbutton")
async def delete_subbutton(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    button = data['original_button']
    
    submenus = [getattr(button, f"submdata{i}") for i in range(1, 16) if getattr(button, f"submdata{i}", None)]
    if not submenus:
        await callback.message.edit_text("Подменю пусто.")
        await callback.answer()
        return
    
    text = "Выберите подкнопку для удаления:\n"
    keyboard = InlineKeyboardBuilder()
    for i, sub in enumerate(submenus, start=1):
        keyboard.row(InlineKeyboardButton(text=f"{i}. {sub}", callback_data=f"confirm_delete:{sub}"))
    keyboard.row(InlineKeyboardButton(text="Назад", callback_data="edit_submenu"))
    
    await callback.message.edit_text(text, reply_markup=keyboard.as_markup())
    await callback.answer()

@edit_button_router.callback_query(F.data.startswith("confirm_delete:"))
async def confirm_delete_subbutton(callback: CallbackQuery, state: FSMContext):
    subbutton_data = callback.data.split(":")[1]
    data = await state.get_data()
    button = data['original_button']
    
    for i in range(1, 16):
        if getattr(button, f"submdata{i}", None) == subbutton_data:
            updates = {f"submdata{i}": None}
            await update_button(state, updates)
            await state.update_data(pending_updates=updates)
            break
    
    await callback.message.edit_text(f"Подкнопка {subbutton_data} удалена.")
    await confirm_changes(callback.message, state)
    await state.set_state(EditButtonStates.SELECT_PARAMETER)
    await callback.answer()

async def update_button(state: FSMContext, updates: dict):
    data = await state.get_data()
    button_data = data['button_data']
    
    try:
        async with async_session() as session:
            query = (
                buttons_table.update().
                where(buttons_table.c.data == button_data).
                values(**updates)
            )
            await session.execute(query)
            await session.commit()
    except Exception as e:
        raise ValueError(f"Ошибка при обновлении записи: {e}")

async def get_button_by_data(data: str):
    async with async_session() as session:
        query = select(buttons_table).where(buttons_table.c.data == data)
        result = await session.execute(query)
        return result.fetchone()
