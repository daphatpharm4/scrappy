import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Optional

from .config import get_service_settings

correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        base: Dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)
        correlation_id = correlation_id_var.get()
        if correlation_id:
            base["correlation_id"] = correlation_id
        for key, value in getattr(record, "extra_data", {}).items():
            base[key] = value
        return json.dumps(base)


def setup_logging(level: str | None = None) -> None:
    settings = get_service_settings()
    log_level = level or settings.log_level
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers.clear()
    root.addHandler(handler)


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    cid = correlation_id or str(uuid.uuid4())
    correlation_id_var.set(cid)
    return cid


def get_correlation_id() -> Optional[str]:
    return correlation_id_var.get()


def log_with_extra(logger: logging.Logger, level: int, message: str, **extra: Any) -> None:
    logger.log(level, message, extra={"extra_data": extra})
