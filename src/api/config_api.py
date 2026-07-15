import os

from dotenv import load_dotenv

load_dotenv()


class ConfigApi:
    MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", 10)) * 1024 * 1024
    INGESTION_ROOT: str = os.getenv("INGESTION_ROOT", "/var/home")
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM")


config_api = ConfigApi()
