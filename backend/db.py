import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from .settings import get_settings


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_columns(conn: sqlite3.Connection) -> None:
    cur = conn.execute("PRAGMA table_info(runs)")
    cols = {row[1] for row in cur.fetchall()}
    if "makeup_output" not in cols:
        conn.execute("ALTER TABLE runs ADD COLUMN makeup_output TEXT")


def init_db() -> None:
    settings = get_settings()
    os.makedirs(os.path.dirname(settings.database_path), exist_ok=True)
    with sqlite3.connect(settings.database_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
              id TEXT PRIMARY KEY,
              user_id TEXT,
              status TEXT NOT NULL,
              drama_input TEXT NOT NULL,
              layer1_output TEXT,
              makeup_output TEXT,
              layer2_output TEXT,
              layer3_output TEXT,
              error_code TEXT,
              error_message TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_runs_status ON runs (status)"
        )
        _ensure_columns(conn)
        conn.commit()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    settings = get_settings()
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def create_run(drama_input: str, user_id: str | None = None) -> str:
    run_id = str(uuid.uuid4())
    now = _utc_now()
    with connect() as conn:
        _ensure_columns(conn)
        conn.execute(
            """
            INSERT INTO runs (
              id, user_id, status, drama_input,
              layer1_output, makeup_output, layer2_output, layer3_output,
              error_code, error_message, created_at, updated_at
            ) VALUES (?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, ?, ?)
            """,
            (run_id, user_id, "draft", drama_input, now, now),
        )
        conn.commit()
    return run_id


def update_run(
    run_id: str,
    *,
    status: str | None = None,
    layer1_output: dict[str, Any] | None = None,
    makeup_output: dict[str, Any] | None = None,
    layer2_output: dict[str, Any] | None = None,
    layer3_output: dict[str, Any] | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    clear_errors: bool = False,
) -> None:
    fields: list[str] = []
    values: list[Any] = []
    if clear_errors:
        fields.append("error_code = NULL")
        fields.append("error_message = NULL")
    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if layer1_output is not None:
        fields.append("layer1_output = ?")
        values.append(json.dumps(layer1_output, ensure_ascii=False))
    if makeup_output is not None:
        fields.append("makeup_output = ?")
        values.append(json.dumps(makeup_output, ensure_ascii=False))
    if layer2_output is not None:
        fields.append("layer2_output = ?")
        values.append(json.dumps(layer2_output, ensure_ascii=False))
    if layer3_output is not None:
        fields.append("layer3_output = ?")
        values.append(json.dumps(layer3_output, ensure_ascii=False))
    if error_code is not None:
        fields.append("error_code = ?")
        values.append(error_code)
    if error_message is not None:
        fields.append("error_message = ?")
        values.append(error_message)
    fields.append("updated_at = ?")
    values.append(_utc_now())
    values.append(run_id)
    sql = f"UPDATE runs SET {', '.join(fields)} WHERE id = ?"
    with connect() as conn:
        _ensure_columns(conn)
        conn.execute(sql, values)
        conn.commit()


def get_run(run_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        _ensure_columns(conn)
        cur = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
        row = cur.fetchone()
    if not row:
        return None
    d = dict(row)
    for key in ("layer1_output", "makeup_output", "layer2_output", "layer3_output"):
        raw = d.get(key)
        if raw:
            d[key] = json.loads(raw)
        else:
            d[key] = None
    return d
