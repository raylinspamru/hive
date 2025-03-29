# bot/handlers.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, FSInputFile
from utils.database import buttons_table, async_session
from sqlalchemy.future import select
from aiogram.utils.keyboard import InlineKeyboardBuilder
import os
import logging

router = Router()

# Асинхронная функция для получения записи из БД по Data
async def get_button_by_data(data: str):
    async with async_session() as session:
        query = select(buttons_table).where(buttons_table.c.data == data)
        result = await session.execute(query)
        return result.fetchone()

# Проверка существования кнопки
async def check_button_exists(data: str) -> bool:
    button = await get_button_by_data(data)
    return button is not None

# Обработчик для возврата в главное меню
@router.callback_query(F.data == "back_to_start")
async def handle_back_to_start(callback: CallbackQuery):
    # Удаляем текущее сообщение и отправляем в начало (будет обработано в basic_handlers)
    await callback.message.delete()
    await callback.bot.send_message(callback.from_user.id, "/start")
    await callback.answer()

# Обработчик для возврата к родительскому меню
@router.callback_query(F.data.startswith("back_to:"))
async def handle_back_button(callback: CallbackQuery):
    parent_data = callback.data.split(":")[1]
    
    parent_button = await get_button_by_data(parent_data)
    if not parent_button:
        await callback.answer("Родительская кнопка не найдена", show_alert=True)
        return

    if parent_button.type == "menu":
        keyboard = InlineKeyboardBuilder()
        for i in range(1, 16):
            submdata = getattr(parent_button, f"submdata{i}", None)
            if submdata and submdata != "0":
                sub_button = await get_button_by_data(submdata)
                if sub_button:
                    keyboard.row(
                        InlineKeyboardButton(text=sub_button.name, callback_data=submdata)
                    )
        
        if parent_button.parentdataorcommand != "start":
            keyboard.row(
                InlineKeyboardButton(
                    text="Назад",
                    callback_data=f"back_to:{parent_button.parentdataorcommand}"
                )
            )
        keyboard.row(
            InlineKeyboardButton(text="В главное меню", callback_data="back_to_start")
        )

        reply_markup = keyboard.as_markup()
        text = parent_button.text or "Меню"

        try:
            await callback.message.edit_text(text, reply_markup=reply_markup)
        except Exception as e:
            logging.error(f"Ошибка при редактировании сообщения: {e}")
            await callback.message.answer(text, reply_markup=reply_markup)
            await callback.message.delete()

        await callback.answer()

    elif parent_button.type == "text":
        reply_markup = InlineKeyboardBuilder().row(
            InlineKeyboardButton(
                text="Назад",
                callback_data=f"back_to:{parent_button.parentdataorcommand}"
            )
        ).as_markup()

        await callback.message.answer(
            text=parent_button.text,
            reply_markup=reply_markup
        )
        await callback.message.delete()
        await callback.answer()

    elif parent_button.type == "textimage":
        photo_path = f"img/{parent_button.data}.jpg"
        if not os.path.exists(photo_path):
            await callback.answer("Изображение не найдено", show_alert=True)
            return

        reply_markup = InlineKeyboardBuilder().row(
            InlineKeyboardButton(
                text="Назад",
                callback_data=f"back_to:{parent_button.parentdataorcommand}"
            )
        ).as_markup()

        await callback.message.answer_photo(
            photo=FSInputFile(photo_path),
            caption=parent_button.text,
            reply_markup=reply_markup
        )
        await callback.message.delete()
        await callback.answer()

    elif parent_button.type == "url":
        reply_markup = InlineKeyboardBuilder().row(
            InlineKeyboardButton(text=parent_button.name, url=parent_button.text),
            InlineKeyboardButton(
                text="Назад",
                callback_data=f"back_to:{parent_button.parentdataorcommand}"
            )
        ).as_markup()

        await callback.message.answer(
            text="Перейдите по ссылке:",
            reply_markup=reply_markup
        )
        await callback.message.delete()
        await callback.answer()

# Обработчик команд и callback-запросов для динамического меню
@router.message(F.text.startswith('/'))
@router.callback_query()
async def handle_button(event):
    if isinstance(event, Message):
        button_data = event.text[1:]  # Убираем слэш для команд
    elif isinstance(event, CallbackQuery):
        button_data = event.data
        if button_data.startswith("back_to:") or button_data == "back_to_start":
            return  # Пропускаем, если это возврат
    else:
        return

    if not await check_button_exists(button_data):
        if isinstance(event, CallbackQuery):
            await event.answer("Кнопка не найдена", show_alert=True)
        return

    button = await get_button_by_data(button_data)
    command, type_ = button.command, button.type

    if command == 1:  # Вызывается по команде
        if type_ == "menu":
            await cmd_menu_handler(event, button)
        elif type_ == "text":
            await cmd_text_handler(event, button)
        elif type_ == "textimage":
            await cmd_textimage_handler(event, button)
    elif command == 0:  # Вызывается по нажатию другой кнопки
        if type_ == "menu":
            await data_menu_handler(event, button)
        elif type_ == "text":
            await data_text_handler(event, button)
        elif type_ == "textimage":
            await data_textimage_handler(event, button)
        elif type_ == "url":
            await data_url_handler(event, button)

# Обработчики для команд
async def cmd_menu_handler(event, button):
    keyboard = InlineKeyboardBuilder()
    for i in range(1, 16):
        submdata = getattr(button, f"submdata{i}", None)
        if submdata and submdata != "0":
            sub_button = await get_button_by_data(submdata)
            if sub_button:
                if sub_button.type == "url":
                    keyboard.row(InlineKeyboardButton(text=sub_button.name, url=sub_button.text))
                else:
                    keyboard.row(InlineKeyboardButton(text=sub_button.name, callback_data=submdata))
    
    keyboard.row(InlineKeyboardButton(text="В главное меню", callback_data="back_to_start"))
    reply_markup = keyboard.as_markup()
    text = button.text or "Меню"

    if isinstance(event, Message):
        await event.answer(text, reply_markup=reply_markup)
    elif isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=reply_markup)
        await event.answer()

async def cmd_text_handler(event, button):
    reply_markup = InlineKeyboardBuilder().row(
        InlineKeyboardButton(text="В главное меню", callback_data="back_to_start")
    ).as_markup()

    if isinstance(event, Message):
        await event.answer(button.text, reply_markup=reply_markup)
    elif isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(button.text, reply_markup=reply_markup)
        except Exception as e:
            logging.error(f"Ошибка при редактировании сообщения: {e}")
            await event.message.answer(button.text, reply_markup=reply_markup)
            await event.message.delete()
        await event.answer()

async def cmd_textimage_handler(event, button):
    photo_path = f"img/{button.data}.jpg"
    if not os.path.exists(photo_path):
        await event.answer("Изображение не найдено", show_alert=True)
        return

    reply_markup = InlineKeyboardBuilder().row(
        InlineKeyboardButton(text="В главное меню", callback_data="back_to_start")
    ).as_markup()

    if isinstance(event, Message):
        await event.answer_photo(
            photo=FSInputFile(photo_path),
            caption=button.text,
            reply_markup=reply_markup
        )
    elif isinstance(event, CallbackQuery):
        await event.message.answer_photo(
            photo=FSInputFile(photo_path),
            caption=button.text,
            reply_markup=reply_markup
        )
        await event.message.delete()
        await event.answer()

# Обработчики для кнопок
async def data_menu_handler(event, button):
    keyboard = InlineKeyboardBuilder()
    for i in range(1, 16):
        submdata = getattr(button, f"submdata{i}", None)
        if submdata and submdata != "0":
            sub_button = await get_button_by_data(submdata)
            if sub_button:
                if sub_button.type == "url":
                    keyboard.row(InlineKeyboardButton(text=sub_button.name, url=sub_button.text))
                else:
                    keyboard.row(InlineKeyboardButton(text=sub_button.name, callback_data=submdata))

    keyboard.row(InlineKeyboardButton(text="Назад", callback_data=f"back_to:{button.parentdataorcommand}"))
    reply_markup = keyboard.as_markup()
    text = button.text or "Меню"

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=reply_markup)
        await event.answer()

async def data_text_handler(event, button):
    reply_markup = InlineKeyboardBuilder().row(
        InlineKeyboardButton(text="Назад", callback_data=f"back_to:{button.parentdataorcommand}")
    ).as_markup()

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(button.text, reply_markup=reply_markup)
        await event.answer()

async def data_textimage_handler(event: CallbackQuery, button):
    photo_path = f"img/{button.data}.jpg"
    if not os.path.exists(photo_path):
        await event.answer("Изображение не найдено", show_alert=True)
        return

    reply_markup = InlineKeyboardBuilder().row(
        InlineKeyboardButton(text="Назад", callback_data=f"back_to:{button.parentdataorcommand}")
    ).as_markup()

    await event.message.answer_photo(
        photo=FSInputFile(photo_path),
        caption=button.text,
        reply_markup=reply_markup
    )
    await event.message.delete()
    await event.answer()

async def data_url_handler(event, button):
    reply_markup = InlineKeyboardBuilder().row(
        InlineKeyboardButton(text=button.name, url=button.text),
        InlineKeyboardButton(text="Назад", callback_data=f"back_to:{button.parentdataorcommand}")
    ).as_markup()

    if isinstance(event, CallbackQuery):
        await event.message.edit_text("Перейдите по ссылке:", reply_markup=reply_markup)
        await event.answer()