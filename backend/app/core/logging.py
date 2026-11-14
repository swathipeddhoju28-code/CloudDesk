import json
import logging
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Iterator, TextIO


_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_workflow_id: ContextVar[str | None] = ContextVar("workflow_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, timezone.utc)
        payload: dict[str, object] = {
            "timestamp": timestamp.isoformat(timespec="milliseconds").replace(
                "+00:00", "Z"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": _request_id.get(),
            "workflow_id": _workflow_id.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, ensure_ascii=False)


@contextmanager
def log_context(
    *, request_id: str | None = None, workflow_id: str | None = None
) -> Iterator[None]:
    tokens: list[tuple[ContextVar[str | None], Token[str | None]]] = []
    if request_id is not None:
        tokens.append((_request_id, _request_id.set(request_id)))
    if workflow_id is not None:
        tokens.append((_workflow_id, _workflow_id.set(workflow_id)))
    try:
        yield
    finally:
        for variable, token in reversed(tokens):
            variable.reset(token)


def setup_logging(
    level: int | str = logging.INFO, *, stream: TextIO | None = None
) -> None:
    if isinstance(level, str):
        resolved_level = logging.getLevelName(level.upper())
        if not isinstance(resolved_level, int):
            raise ValueError(f"Unknown logging level: {level}")
    else:
        resolved_level = level

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)
    root_logger.setLevel(resolved_level)
