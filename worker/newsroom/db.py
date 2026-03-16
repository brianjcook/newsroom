from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import pymysql

from .config import DatabaseConfig


@contextmanager
def connect(config: DatabaseConfig) -> Iterator[pymysql.connections.Connection]:
    connection = pymysql.connect(
        host=config.host,
        port=config.port,
        user=config.user,
        password=config.password,
        database=config.name,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
