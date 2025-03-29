from aiogram.types import CallbackQuery

class IsAdminPanelCallback:
    def __init__(self, admin_data: list[str]):
        self.admin_data = admin_data

    async def __call__(self, callback: CallbackQuery) -> bool:
        return callback.data in self.admin_data