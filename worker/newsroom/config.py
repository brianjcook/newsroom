from __future__ import annotations

import os
from dataclasses import dataclass


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


@dataclass(frozen=True)
class WorkerConfig:
    database: DatabaseConfig
    fetch_user_agent: str
    source_discovery_enabled: bool
    agenda_center_url: str
    documents_dir: str
    logs_dir: str


def load_config() -> WorkerConfig:
    return WorkerConfig(
        database=DatabaseConfig(
            host=_env("NEWSROOM_DB_HOST", "localhost"),
            port=int(_env("NEWSROOM_DB_PORT", "3306")),
            name=_env("NEWSROOM_DB_NAME", "bricoo10_newsroom"),
            user=_env("NEWSROOM_DB_USER"),
            password=_env("NEWSROOM_DB_PASSWORD"),
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
        documents_dir=_env("NEWSROOM_DOCUMENTS_DIR", "storage/documents"),
        logs_dir=_env("NEWSROOM_LOGS_DIR", "storage/logs"),
    )
