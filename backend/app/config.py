from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Energy Prediction System"
    app_version: str = "0.1.0"
    database_url: str = "mongodb://localhost:27017/energy"
    jwt_secret_key: str = "CHANGE_ME"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60
    class Config:
        env_file = ".env"
