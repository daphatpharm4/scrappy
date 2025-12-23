import logging
import time
from functools import wraps
from typing import Any, Callable, TypeVar

T = TypeVar("T")
logger = logging.getLogger(__name__)


class RetryConfig:
    def __init__(self, attempts: int = 3, backoff_seconds: float = 1.5):
        self.attempts = attempts
        self.backoff_seconds = backoff_seconds


def retry(config: RetryConfig) -> Callable[[Callable[..., T]], Callable[..., T]]:
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001
                    attempt += 1
                    if attempt >= config.attempts:
                        logger.error("Max retries exceeded", exc_info=exc)
                        raise
                    sleep_for = config.backoff_seconds * attempt
                    logger.warning(
                        "Retrying after failure", extra={"extra_data": {"attempt": attempt, "sleep_for": sleep_for}}
                    )
                    time.sleep(sleep_for)
        return wrapper

    return decorator
