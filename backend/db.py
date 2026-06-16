from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable

import pyodbc

from config import config


@contextmanager
def get_connection():
    conn = pyodbc.connect(config.odbc_connection_string(), timeout=5)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def to_json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def rows_to_dicts(cursor: pyodbc.Cursor) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description or []]
    return [
        {columns[index]: to_json_value(value) for index, value in enumerate(row)}
        for row in cursor.fetchall()
    ]


def execute_query(sql: str, params: Iterable[Any] | None = None) -> list[dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, list(params or []))
        return rows_to_dicts(cursor)


def execute_non_query(sql: str, params: Iterable[Any] | None = None) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, list(params or []))
        return cursor.rowcount


def insert_and_return_id(table: str, columns: list[str], values: list[Any], pk: str) -> Any:
    quoted_cols = ", ".join(f"[{column}]" for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    sql = f"""
        INSERT INTO dbo.{table} ({quoted_cols})
        OUTPUT INSERTED.[{pk}]
        VALUES ({placeholders});
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, values)
        return to_json_value(cursor.fetchone()[0])
