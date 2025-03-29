from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    BOT_TOKEN: str
    ADMIN_IDS: list[int] = []
    DATABASE_URL: str = "sqlite+aiosqlite:///bot.db"
    DIRECTOR_LOGIN: str = "director"
    DIRECTOR_PASSWORD: str = "artepass758"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()