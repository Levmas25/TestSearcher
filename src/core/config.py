from functools import cache

from pydantic import SecretStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class DBSettings(BaseSettings):

    username: str
    host: str
    port: int = Field(gt=0, lt=65536)
    name: str
    password: SecretStr
    debug: bool = False

    
    @property
    def async_url(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.username,
            port=self.port,
            database=self.name,
            password=self.password.get_secret_value()
        )


@cache
def get_settings():
    return DBSettings()  # pyright: ignore[reportCallIssue]