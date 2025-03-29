# bot/view_buttons.py

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from utils.database import buttons_table, async_session
from sqlalchemy.future import select
from aiogram.utils.keyboard import InlineKeyboardBuilder

view_buttons_router = Router()

ITEMS_PER_PAGE = 3  # Максимум 3 кнопки на страницу
MAX_MESSAGE_LENGTH = 4096  # Лимит Telegram

# Определяем состояния для ввода номера страницы и поиска
class ViewStates(StatesGroup):
    WAITING_FOR_PAGE = State()
    WAITING_FOR_SEARCH_VALUE = State()

# Функция для получения кнопок с пагинацией
async def get_paginated_buttons(page: int, limit: int = ITEMS_PER_PAGE):
    offset = page * ITEMS_PER_PAGE
    async with async_session() as session:
        query = select(buttons_table).offset(offset).limit(limit)
        result = await session.execute(query)
        return result.fetchall()

# Функция для получения общего количества кнопок
async def get_total_buttons():
    async with async_session() as session:
        query = select(buttons_table)
        result = await session.execute(query)
        return len(result.fetchall())

# Функция для поиска кнопок по критерию
async def search_buttons(criterion: str, value: str):
    async with async_session() as session:
        if criterion == "data":
            query = select(buttons_table).where(buttons_table.c.data.ilike(f"%{value}%"))
        elif criterion == "command":
            query = select(buttons_table).where(buttons_table.c.command == (1 if value.lower() in ["команда", "1"] else 0))
        elif criterion == "name":
            query = select(buttons_table).where(buttons_table.c.name.ilike(f"%{value}%"))
        else:
            return []
        result = await session.execute(query)
        return result.fetchall()

# Функция для формирования текста кнопок с динамическим количеством
def format_buttons(buttons, max_length=MAX_MESSAGE_LENGTH):
    text = ""
    valid_buttons = []
    for button in buttons:
        name = button.name if button.name and button.name != "0" else "Нет названия"
        command_text = f"Вызывается по команде - /{button.parentdataorcommand}" if button.command == 1 else f"Вызывается по нажатию кнопки в меню - {button.parentdataorcommand}"
        button_type = button.type
        button_text = button.text or "Отсутствует"
        if len(button_text) > 100:
            button_text = button_text[:100] + "... (обрезано)"
        
        submenus = [getattr(button, f"submdata{i}") for i in range(1, 16) if getattr(button, f"submdata{i}")]
        submenu_text = ", ".join(submenus) if submenus else "Отсутствуют"

        button_text_entry = (
            f"🏷 *Название*: {name} | *Data*: {button.data}\n"
            f"🔧 *Тип*: {button_type}\n"
            f"📞 *Вызов*: {command_text}\n"
            f"📝 *Текст*: {button_text}\n"
            f"🌐 *Подменю*: {submenu_text}\n"
            "────────────────────\n"
        )
        
        if len(text) + len(button_text_entry) <= max_length - 50:  # 50 - запас на заголовок
            text += button_text_entry
            valid_buttons.append(button)
        else:
            break
    
    return text.strip(), len(valid_buttons), valid_buttons

# Обработчик для просмотра кнопок с пагинацией
@view_buttons_router.callback_query(F.data.startswith("view_buttons"))
async def show_buttons(callback: CallbackQuery, state: FSMContext = None):
    await callback.message.delete()
    page = int(callback.data.split(":")[1]) if ":" in callback.data else 0
    
    buttons = await get_paginated_buttons(page)
    total_buttons = await get_total_buttons()
    total_pages = (total_buttons + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    if not buttons:
        await callback.message.answer("Список кнопок пуст.")
        return

    text, items_displayed, _ = format_buttons(buttons)
    text = f"**Страница {page + 1} из {total_pages}**\n\n" + text

    if len(text) > MAX_MESSAGE_LENGTH:
        await callback.message.answer("Слишком много данных для отображения.")
        return

    keyboard = InlineKeyboardBuilder()
    if page > 0:
        keyboard.button(text="⬅ Предыдущая", callback_data=f"view_buttons:{page - 1}")
        if page < total_pages - 1:
            keyboard.button(text="Следующая ➡", callback_data=f"view_buttons:{page + 1}")
    elif page < total_pages - 1:
        keyboard.button(text="Следующая ➡", callback_data=f"view_buttons:{page + 1}")
    
    if page > 0 or page < total_pages - 1:
        if page > 0:
            keyboard.button(text="⏮ Первая", callback_data="view_buttons:0")
        if page < total_pages - 1:
            keyboard.button(text="Последняя ⏭", callback_data=f"view_buttons:{total_pages - 1}")
    
    keyboard.button(text="Ввести номер страницы", callback_data="input_page")
    keyboard.button(text="Искать кнопку по", callback_data="search_button")
    keyboard.button(text="Назад", callback_data="back_to_dynamic_menu")
    keyboard.adjust(2, 2, 1, 1, 1)

    await callback.message.answer(text, reply_markup=keyboard.as_markup(), parse_mode="Markdown")
    await callback.answer()

# Обработчик для навигации по всем кнопкам
@view_buttons_router.callback_query(F.data.startswith("view_buttons:"))
async def navigate_buttons(callback: CallbackQuery, state: FSMContext = None):
    page = int(callback.data.split(":")[1])
    
    buttons = await get_paginated_buttons(page)
    total_buttons = await get_total_buttons()
    total_pages = (total_buttons + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    if not buttons:
        await callback.message.edit_text("Список кнопок пуст.")
        return

    text, items_displayed, _ = format_buttons(buttons)
    text = f"**Страница {page + 1} из {total_pages}**\n\n" + text

    if len(text) > MAX_MESSAGE_LENGTH:
        await callback.message.edit_text("Слишком много данных для отображения.")
        return

    keyboard = InlineKeyboardBuilder()
    if page > 0:
        keyboard.button(text="⬅ Предыдущая", callback_data=f"view_buttons:{page - 1}")
        if page < total_pages - 1:
            keyboard.button(text="Следующая ➡", callback_data=f"view_buttons:{page + 1}")
    elif page < total_pages - 1:
        keyboard.button(text="Следующая ➡", callback_data=f"view_buttons:{page + 1}")
    
    if page > 0 or page < total_pages - 1:
        if page > 0:
            keyboard.button(text="⏮ Первая", callback_data="view_buttons:0")
        if page < total_pages - 1:
            keyboard.button(text="Последняя ⏭", callback_data=f"view_buttons:{total_pages - 1}")
    
    keyboard.button(text="Ввести номер страницы", callback_data="input_page")
    keyboard.button(text="Искать кнопку по", callback_data="search_button")
    keyboard.button(text="Назад", callback_data="back_to_dynamic_menu")
    keyboard.adjust(2, 2, 1, 1, 1)

    await callback.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode="Markdown")
    await callback.answer()

# Обработчик для ввода номера страницы
@view_buttons_router.callback_query(F.data == "input_page")
async def start_input_page(callback: CallbackQuery, state: FSMContext):
    total_buttons = await get_total_buttons()
    total_pages = (total_buttons + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    await callback.message.delete()  # Удаляем предыдущее меню просмотра кнопок
    await callback.message.answer(
        f"🔢 *Введите номер страницы (от 1 до {total_pages}):*",
        reply_markup=InlineKeyboardBuilder()
        .button(text="⬅ Назад", callback_data="view_buttons:0")
        .as_markup(),
        parse_mode="Markdown"
    )
    await state.set_state(ViewStates.WAITING_FOR_PAGE)
    await callback.answer()

# Обработчик ввода номера страницы
@view_buttons_router.message(ViewStates.WAITING_FOR_PAGE)
async def process_page_input(message: Message, state: FSMContext):
    try:
        page_num = int(message.text.strip()) - 1
        total_buttons = await get_total_buttons()
        total_pages = (total_buttons + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

        if 0 <= page_num < total_pages:
            buttons = await get_paginated_buttons(page_num)
            text, items_displayed, _ = format_buttons(buttons)
            text = f"**Страница {page_num + 1} из {total_pages}**\n\n" + text

            keyboard = InlineKeyboardBuilder()
            if page_num > 0:
                keyboard.button(text="⬅ Предыдущая", callback_data=f"view_buttons:{page_num - 1}")
                if page_num < total_pages - 1:
                    keyboard.button(text="Следующая ➡", callback_data=f"view_buttons:{page_num + 1}")
            elif page_num < total_pages - 1:
                keyboard.button(text="Следующая ➡", callback_data=f"view_buttons:{page_num + 1}")
            
            if page_num > 0 or page_num < total_pages - 1:
                if page_num > 0:
                    keyboard.button(text="⏮ Первая", callback_data="view_buttons:0")
                if page_num < total_pages - 1:
                    keyboard.button(text="Последняя ⏭", callback_data=f"view_buttons:{total_pages - 1}")
            
            keyboard.button(text="Ввести номер страницы", callback_data="input_page")
            keyboard.button(text="Искать кнопку по", callback_data="search_button")
            keyboard.button(text="Назад", callback_data="back_to_dynamic_menu")
            keyboard.adjust(2, 2, 1, 1, 1)

            await message.answer(text, reply_markup=keyboard.as_markup(), parse_mode="Markdown")
        else:
            await message.answer(f"⚠️ Пожалуйста, введите номер от 1 до {total_pages}.")
    except ValueError:
        await message.answer("⚠️ Пожалуйста, введите корректный номер страницы (число).")
    finally:
        await state.clear()

# Обработчик кнопки "Искать кнопку по"
@view_buttons_router.callback_query(F.data == "search_button")
async def show_search_menu(callback: CallbackQuery):
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="По Data", callback_data="search_by:data")
    keyboard.button(text="По типу вызова", callback_data="search_by:command")
    keyboard.button(text="По названию", callback_data="search_by:name")
    keyboard.button(text="⬅ Назад", callback_data="back_to_view")
    keyboard.adjust(1)

    await callback.message.edit_text(
        "🔍 *Выберите, по чему искать кнопку:*",
        reply_markup=keyboard.as_markup(),
        parse_mode="Markdown"
    )
    await callback.answer()

# Обработчик выбора критерия поиска
@view_buttons_router.callback_query(F.data.startswith("search_by:"))
async def start_search_by(callback: CallbackQuery, state: FSMContext):
    criterion = callback.data.split(":")[1]
    await state.update_data(search_criterion=criterion)
    
    if criterion == "command":
        await callback.message.edit_text(
            "🔍 *Введите тип вызова* (например, 'команда' или 'кнопка'):",
            reply_markup=InlineKeyboardBuilder()
            .button(text="❌ Отмена поиска", callback_data="cancel_search")
            .as_markup(),
            parse_mode="Markdown"
        )
    else:
        await callback.message.edit_text(
            f"🔍 *Введите значение для поиска по {criterion}:*",
            reply_markup=InlineKeyboardBuilder()
            .button(text="❌ Отмена поиска", callback_data="cancel_search")
            .as_markup(),
            parse_mode="Markdown"
        )
    
    await state.set_state(ViewStates.WAITING_FOR_SEARCH_VALUE)
    await callback.answer()

# Обработчик ввода значения для поиска
@view_buttons_router.message(ViewStates.WAITING_FOR_SEARCH_VALUE)
async def process_search_input(message: Message, state: FSMContext):
    value = message.text.strip()
    data = await state.get_data()
    criterion = data.get("search_criterion")

    buttons = await search_buttons(criterion, value)
    await message.delete()  # Удаляем сообщение с запросом ввода

    if not buttons:
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="🔍 Искать ещё раз", callback_data="search_button")
        keyboard.button(text="❌ Отмена поиска", callback_data="cancel_search")
        keyboard.adjust(1)
        await message.answer(
            f"⚠️ *Ничего не найдено по {criterion}: '{value}'*",
            reply_markup=keyboard.as_markup(),
            parse_mode="Markdown"
        )
        await state.clear()
        return

    total_search_results = len(buttons)
    total_search_pages = (total_search_results + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    if total_search_results <= ITEMS_PER_PAGE:
        text, items_displayed, _ = format_buttons(buttons)
        text = f"**🔍 Результаты поиска по {criterion}: '{value}'**\n\n" + text

        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="⬅ Назад", callback_data="cancel_search")
        keyboard.adjust(1)

        await message.answer(text, reply_markup=keyboard.as_markup(), parse_mode="Markdown")
    else:
        # Если слишком много результатов, переходим в меню поиска с пагинацией
        await state.update_data(search_results=buttons, search_criterion=criterion, search_value=value)
        await show_search_results(callback=message, state=state, page=0)

    await state.clear()

# Обработчик для просмотра результатов поиска с пагинацией
async def show_search_results(callback: Message | CallbackQuery, state: FSMContext, page: int):
    data = await state.get_data()
    buttons = data.get("search_results", [])
    criterion = data.get("search_criterion")
    value = data.get("search_value")
    total_search_results = len(buttons)
    total_search_pages = (total_search_results + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE

    start_idx = page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, total_search_results)
    page_buttons = buttons[start_idx:end_idx]

    text, items_displayed, _ = format_buttons(page_buttons)
    text = f"**🔍 Результаты поиска по {criterion}: '{value}' (Страница {page + 1} из {total_search_pages})**\n\n" + text

    keyboard = InlineKeyboardBuilder()
    if page > 0:
        keyboard.button(text="⬅ Предыдущая", callback_data=f"search_page:{page - 1}")
        if page < total_search_pages - 1:
            keyboard.button(text="Следующая ➡", callback_data=f"search_page:{page + 1}")
    elif page < total_search_pages - 1:
        keyboard.button(text="Следующая ➡", callback_data=f"search_page:{page + 1}")
    
    if page > 0 or page < total_search_pages - 1:
        if page > 0:
            keyboard.button(text="⏮ Первая", callback_data="search_page:0")
        if page < total_search_pages - 1:
            keyboard.button(text="Последняя ⏭", callback_data=f"search_page:{total_search_pages - 1}")
    
    keyboard.button(text="⬅ Назад ко всем кнопкам", callback_data="cancel_search")
    keyboard.adjust(2, 2, 1)

    if isinstance(callback, Message):
        await callback.answer(text, reply_markup=keyboard.as_markup(), parse_mode="Markdown")
    else:
        await callback.message.edit_text(text, reply_markup=keyboard.as_markup(), parse_mode="Markdown")
        await callback.answer()

# Обработчик навигации по страницам результатов поиска
@view_buttons_router.callback_query(F.data.startswith("search_page:"))
async def navigate_search_results(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split(":")[1])
    await show_search_results(callback, state, page)

# Обработчик возврата к просмотру кнопок
@view_buttons_router.callback_query(F.data == "back_to_view")
async def back_to_view(callback: CallbackQuery):
    await show_buttons(callback)  # Возвращаемся к первой странице

# Обработчик отмены поиска
@view_buttons_router.callback_query(F.data == "cancel_search")
async def cancel_search(callback: CallbackQuery):
    await show_buttons(callback)  # Возвращаемся к первой странице

# Обработчик кнопки "Назад"
@view_buttons_router.callback_query(F.data == "back_to_dynamic_menu")
async def back_to_dynamic_menu(callback: CallbackQuery):
    from bot.adminpanel import DYNAMIC_MENU
    await callback.message.edit_text(
        "Вы можете управлять динамическим меню:",
        reply_markup=DYNAMIC_MENU
    )
    await callback.answer()