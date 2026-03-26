"""Structured logging configuration for GenomeInsight (P4-21b).

Configures structlog to write log entries to both console (for development)
and the ``log_entries`` table in reference.db (for the admin panel log explorer).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

import structlog


def _db_processor_factory(engine_getter: callable) -> callable:
    """Create a structlog processor that writes log entries to reference.db.

    Args:
        engine_getter: Callable returning the reference DB SQLAlchemy engine.
            Deferred so the engine doesn't need to exist at import time.
    """

    def db_processor(
        logger: structlog.types.WrappedLogger,
        method_name: str,
        event_dict: structlog.types.EventDict,
    ) -> structlog.types.EventDict:
        """Write each log entry to the log_entries table."""
        try:
            engine = engine_getter()
            if engine is None:
                return event_dict

            import sqlalchemy as sa

            from backend.db.tables import log_entries

            level = method_name.upper()
            logger_name = event_dict.get("logger", event_dict.get("_logger", ""))
            message = event_dict.get("event", "")

            # Collect extra structured data (exclude internal keys)
            _internal = {
                "event",
                "logger",
                "_logger",
                "timestamp",
                "level",
                "_record",
                "_from_structlog",
            }
            extra = {k: v for k, v in event_dict.items() if k not in _internal}
            extra_json = json.dumps(extra, default=str) if extra else None

            with engine.begin() as conn:
                conn.execute(
                    sa.insert(log_entries).values(
                        timestamp=datetime.now(UTC),
                        level=level,
                        logger=str(logger_name),
                        message=str(message),
                        event_data=extra_json,
                    )
                )
        except Exception:
            # Never let logging failures crash the app
            pass

        return event_dict

    return db_processor


def configure_logging(engine_getter: callable | None = None) -> None:
    """Configure structlog with console + optional DB output.

    Args:
        engine_getter: Optional callable returning the reference DB engine.
            If provided, log entries are also persisted to reference.db.
    """
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if engine_getter is not None:
        processors.append(_db_processor_factory(engine_getter))

    processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )

    # Also route stdlib logging through structlog
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
    )
