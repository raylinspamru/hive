# utils/export_excel.py
from io import BytesIO
import pandas as pd
from utils.database import buttons_table, async_session
from sqlalchemy.future import select

from io import BytesIO
import pandas as pd
from utils.database import buttons_table, async_session
from sqlalchemy.future import select

async def export_buttons_to_excel():
    """
    Экспортирует все данные из таблицы buttons_table в файл Excel.
    Возвращает BytesIO объект с файлом.
    """
    async with async_session() as session:
        query = select(buttons_table)
        result = await session.execute(query)
        buttons = result.fetchall()

    if not buttons:
        return None

    data = []
    for button in buttons:
        row = {
            "Data": button.data,
            "Command": "Команда" if button.command == 1 else "Кнопка",
            "Parent/Command": button.parentdataorcommand,
            "Name": button.name,
            "Type": button.type,
            "Text": button.text or "Отсутствует"
        }
        for i in range(1, 16):
            submdata = getattr(button, f"submdata{i}", None)
            row[f"Submenu {i}"] = submdata if submdata else ""
        data.append(row)

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Buttons", index=False)
        worksheet = writer.sheets["Buttons"]
        for i, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.set_column(i, i, min(max_len, 50))

    output.seek(0)
    return output