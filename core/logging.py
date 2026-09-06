import structlog
from structlog.types import Processor

from core.config import settings

IS_PRODUCTION = settings.APP_ENV == "production"


def add_timestamp(logger: object, method_name: str, event_dict: dict) -> dict:
    import datetime
    event_dict["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
    return event_dict


def add_log_level(logger: object, method_name: str, event_dict: dict) -> dict:
    event_dict["level"] = method_name.upper()
    return event_dict


def add_worker_name(logger: object, method_name: str, event_dict: dict) -> dict:
    import sys
    if "worker" not in event_dict:
        module = sys.modules.get("__main__", None)
        if module and hasattr(module, "__name__"):
            event_dict["worker"] = module.__name__.split(".")[-1]
    return event_dict


def remove_pid_and_thread(logger: object, method_name: str, event_dict: dict) -> dict:
    event_dict.pop("process", None)
    event_dict.pop("thread", None)
    return event_dict


def configure_logging(worker_name: str = "") -> structlog.BoundLogger:
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if IS_PRODUCTION:
        shared_processors.extend([
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ])
    else:
        shared_processors.extend([
            structlog.dev.ConsoleRenderer(),
        ])

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    log = structlog.get_logger()
    if worker_name:
        log = log.bind(worker=worker_name)
    return log
