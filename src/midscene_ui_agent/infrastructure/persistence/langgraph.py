"""Owned lifecycle for the official LangGraph SQLite checkpointer."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver


@dataclass
class CheckpointerHandle:
    saver: SqliteSaver
    _manager: AbstractContextManager[SqliteSaver] = field(repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    def close(self) -> None:
        if self._closed:
            return
        self._manager.__exit__(None, None, None)
        self._closed = True

    def __enter__(self) -> "CheckpointerHandle":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()


def sqlite_checkpointer(path: str | Path) -> CheckpointerHandle:
    database = Path(path)
    database.parent.mkdir(parents=True, exist_ok=True)
    manager = SqliteSaver.from_conn_string(str(database))
    saver = manager.__enter__()
    return CheckpointerHandle(saver=saver, _manager=manager)


__all__ = ["CheckpointerHandle", "sqlite_checkpointer"]
