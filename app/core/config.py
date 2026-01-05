from pydantic_settings import BaseSettings
from pathlib import Path
import os

class Settings(BaseSettings):
    MONGO_URI: str
    MONGO_DB_NAME: str
    JWT_SECRET_KEY: str
    JWT_REFRESH_SECRET_KEY: str
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATA_DIR: str = os.path.join(BASE_DIR, "data")

    class Config:
        env_file = ".env"

settings = Settings()
