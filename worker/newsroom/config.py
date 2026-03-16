import os
from dataclasses import dataclass
from typing import Optional


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    password: str
    unix_socket: Optional[str]


@dataclass(frozen=True)
class WorkerConfig:
    database: DatabaseConfig
    fetch_user_agent: str
    source_discovery_enabled: bool
    agenda_center_url: str
    storage_root: str
    documents_dir: str
    extractions_dir: str
    logs_dir: str


def load_config() -> WorkerConfig:
    storage_root = _env("NEWSROOM_SITE_STORAGE_ROOT", "storage")
    return WorkerConfig(
        database=DatabaseConfig(
            host=_env("NEWSROOM_DB_HOST", "localhost"),
            port=int(_env("NEWSROOM_DB_PORT", "3306")),
            name=_env("NEWSROOM_DB_NAME", "bricoo10_newsroom"),
            user=_env("NEWSROOM_DB_USER"),
            password=_env("NEWSROOM_DB_PASSWORD"),
            unix_socket=_env("NEWSROOM_DB_UNIX_SOCKET") or None,
        ),
        fetch_user_agent=_env(
            "NEWSROOM_FETCH_USER_AGENT",
            "WarehamNewsroomBot/0.1 (+https://github.com/brianjcook/newsroom)",
        ),
        source_discovery_enabled=_env("NEWSROOM_SOURCE_DISCOVERY_ENABLED", "1") == "1",
        agenda_center_url=_env(
            "NEWSROOM_AGENDA_CENTER_URL",
            "https://www.wareham.gov/AgendaCenter",
        ),
        storage_root=storage_root,
        documents_dir=_env("NEWSROOM_DOCUMENTS_DIR", f"{storage_root}/documents"),
        extractions_dir=_env("NEWSROOM_EXTRACTIONS_DIR", f"{storage_root}/extractions"),
        logs_dir=_env("NEWSROOM_LOGS_DIR", f"{storage_root}/logs"),
    )
