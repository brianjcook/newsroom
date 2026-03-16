from contextlib import contextmanager
from typing import Iterator

import pymysql

from .config import DatabaseConfig


@contextmanager
def connect(config: DatabaseConfig) -> Iterator[pymysql.connections.Connection]:
    connection_kwargs = {
        "user": config.user,
        "password": config.password,
        "database": config.name,
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": False,
    }

    if config.unix_socket:
        connection_kwargs["unix_socket"] = config.unix_socket
    else:
        connection_kwargs["host"] = config.host
        connection_kwargs["port"] = config.port

    connection = pymysql.connect(**connection_kwargs)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
