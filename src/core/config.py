from functools import cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class DBSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DB_")

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
            password=self.password.get_secret_value(),
            host=self.host
        )


class ElasticSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ELASTIC_")

    host: str = "localhost"
    port: int = Field(default=9200, ge=1, le=65535)
    index: str = "documents"

    @property
    def async_url(self) -> str:
        return f"http://{self.host}:{self.port}"


@cache
def get_settings() -> DBSettings:
    return DBSettings()  # pyright: ignore[reportCallIssue]


@cache
def get_elastic_settings() -> ElasticSettings:
    return ElasticSettings()  # pyright: ignore[reportCallIssue]
