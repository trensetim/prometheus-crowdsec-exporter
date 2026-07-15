import sys
import logging
import structlog

from logging import Logger

_SENSITIVE_KEYS = frozenset({
    "key",
    "api_key",
    "apiKey",
    "password",
    "token",
    "secret"
})

def configure(log_level: str) -> None:

    level = getattr(logging, log_level, logging.INFO)

    # Stdlib root logger → captures third-party library log output too
    # @see https://docs.python.org/3/library/logging.html#logging.basicConfig
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
        force=True,
    )

    # @see  https://www.structlog.org/en/stable/api.html#procs,
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.ExceptionRenderer(),
            _maskSensitiveFields,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False
    )

def getLogger(name: str) -> str:
    return structlog.get_logger(name)

# custom processor - arguments are required by structlog
def _maskSensitiveFields(
    logger: Logger,
    method_name: str,
    event_dict: dict,
) -> dict:
    for key in _SENSITIVE_KEYS:
        if key in event_dict:
            event_dict[key] = "***"
    return event_dict
