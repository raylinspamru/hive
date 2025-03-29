from aiogram import Router, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message, BufferedInputFile
from bot.add_button import add_button_router
from bot.edit_button import edit_button_router
from config import settings
from bot.view_buttons import view_buttons_router, show_buttons
from utils.export_excel import export_buttons_to_excel  # Для скачивания Excel

adminpanel_router = Router()

ADMIN_MENU = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Динамическое меню", callback_data="dynamic_menu")],
    [InlineKeyboardButton(text="В главное меню", callback_data="back_to_start")],
])

DYNAMIC_MENU = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Просмотреть кнопки", callback_data="view_buttons")],
    [InlineKeyboardButton(text="Добавить кнопку", callback_data="add_button")],
    [InlineKeyboardButton(text="Редактировать кнопку", callback_data="edit_button")],
    [InlineKeyboardButton(text="Скачать Excel", callback_data="download_excel")],
    [InlineKeyboardButton(text="Назад", callback_data="back_to_admin_menu")],
])

@adminpanel_router.callback_query(F.data == "view_buttons")
async def handle_view_buttons(callback: CallbackQuery):
    await show_buttons(callback)  # Вызываем функцию из view_buttons.py

# Обработчик команды /admin
@adminpanel_router.message(F.text == "/admin")
async def admin_panel(message: Message):
    if message.from_user.id not in settings.ADMIN_IDS:
        await message.answer("У вас нет прав администратора.")
        return

    await message.delete()
    await message.answer("Выберите действие:", reply_markup=ADMIN_MENU)

# Обработчик кнопки Динамическое меню
@adminpanel_router.callback_query(F.data == "dynamic_menu")
async def manage_dynamic_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "Вы можете управлять динамическим меню:",
        reply_markup=DYNAMIC_MENU
    )
    await callback.answer()

# Функция Скачать Excel
@adminpanel_router.callback_query(F.data == "download_excel")
async def download_excel(callback: CallbackQuery):
    if callback.from_user.id not in settings.ADMIN_IDS:
        await callback.message.answer("У вас нет прав администратора.")
        return

    try:
        # Удаляем текущее сообщение с меню
        await callback.message.delete()

        # Генерируем и отправляем Excel-файл
        excel_file = await export_buttons_to_excel()
        if excel_file:
            input_file = BufferedInputFile(excel_file.getvalue(), filename="buttons.xlsx")
            await callback.message.answer_document(
                document=input_file,
                caption="Полный список кнопок из базы данных."
            )
        else:
            await callback.message.answer("База данных пуста.")

        # Повторно отображаем динамическое меню
        await callback.message.answer(
            "Вы можете управлять динамическим меню:",
            reply_markup=DYNAMIC_MENU
        )

    except Exception as e:
        await callback.message.answer(f"Произошла ошибка: {e}")
    finally:
        await callback.answer()

@adminpanel_router.callback_query(F.data == "back_to_admin_menu")
async def back_to_admin_menu(callback: CallbackQuery):
    await callback.message.edit_text("С возвращением в админ-панель!", reply_markup=ADMIN_MENU)
    await callback.answer()

adminpanel_router.include_router(add_button_router)
adminpanel_router.include_router(edit_button_router)
adminpanel_router.include_router(view_buttons_router)