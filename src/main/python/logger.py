import json
import sys
import logging
from collections import OrderedDict

import structlog

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
            structlog.processors.StackInfoRenderer(),
            structlog.processors.ExceptionRenderer(),
            _maskSensitiveFields,
            structlog.processors.JSONRenderer(serializer=_serialize_json),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=OrderedDict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False
    )

def getLogger(name: str) -> str:
    return structlog.get_logger(name)

def _serialize_json(obj: object, *args, **kwargs) -> str:
    """Custom JSON serializer for structlog: sorts the json object keys in human-readable & consistent/alphabetical order"""
    sorted_obj = OrderedDict()
    key_order = ["level", "event", "logger", "stack_info", "exception"]
    for key in key_order:
        if key in obj:
            sorted_obj[key] = obj[key]
            del obj[key]

    for key in sorted(obj.keys()):
        sorted_obj[key] = obj[key]

    return json.dumps(sorted_obj, *args, **kwargs)

# custom processor - arguments are required by structlog
def _maskSensitiveFields(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict,
) -> dict:
    sensitive_keys = frozenset([
        "key",
        "api_key",
        "apiKey",
        "password",
        "token",
        "secret"
    ])
    for key in sensitive_keys:
        if key in event_dict:
            event_dict[key] = "***"
    return event_dict
