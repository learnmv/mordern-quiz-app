"""Structured logging configuration with correlation IDs."""
import logging
import uuid
import sys
from contextvars import ContextVar
from typing import Any, Optional
from datetime import datetime

# Context variable for correlation ID
correlation_id = ContextVar('correlation_id', default=None)


class CorrelationIdFilter(logging.Filter):
    """Add correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id.get() or 'N/A'
        return True


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        import json

        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "correlation_id": getattr(record, 'correlation_id', 'N/A'),
            "message": record.getMessage(),
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                'thread', 'threadName', 'processName', 'process', 'correlation_id',
                'getMessage', 'message'
            }:
                log_data[key] = value

        return json.dumps(log_data)


def setup_logging(
    level: int = logging.INFO,
    json_format: bool = True,
    correlation_id_enabled: bool = True
) -> None:
    """Setup structured logging for the application.

    Args:
        level: Logging level (default: INFO)
        json_format: Use JSON formatting (default: True)
        correlation_id_enabled: Enable correlation ID tracking (default: True)
    """
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Set formatter
    if json_format:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(correlation_id)s - %(message)s'
        )

    console_handler.setFormatter(formatter)

    # Add correlation ID filter
    if correlation_id_enabled:
        console_handler.addFilter(CorrelationIdFilter())

    root_logger.addHandler(console_handler)

    # Set specific levels for noisy libraries
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    # App logger at DEBUG level
    logging.getLogger('app').setLevel(logging.DEBUG)

    root_logger.info("Logging configured", extra={
        "json_format": json_format,
        "correlation_id_enabled": correlation_id_enabled
    })


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID."""
    return correlation_id.get()


def set_correlation_id(cid: Optional[str] = None) -> str:
    """Set correlation ID.

    Args:
        cid: Correlation ID to set (generates new UUID if None)

    Returns:
        The correlation ID that was set
    """
    cid = cid or str(uuid.uuid4())
    correlation_id.set(cid)
    return cid


def clear_correlation_id() -> None:
    """Clear the correlation ID."""
    correlation_id.set(None)


class LoggingContext:
    """Context manager for logging with correlation ID."""

    def __init__(self, cid: Optional[str] = None, **extra):
        self.cid = cid or str(uuid.uuid4())
        self.extra = extra
        self.token = None

    def __enter__(self):
        self.token = correlation_id.set(self.cid)
        logger = logging.getLogger('app')
        logger.debug("Logging context entered", extra={"correlation_id": self.cid, **self.extra})
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            logger = logging.getLogger('app')
            logger.exception("Exception in logging context", extra=self.extra)
        correlation_id.reset(self.token)


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    **kwargs
) -> None:
    """Log with additional context fields.

    Args:
        logger: Logger instance
        level: Log level
        message: Log message
        **kwargs: Additional fields to include in log
    """
    extra = {
        "correlation_id": get_correlation_id(),
        **kwargs
    }
    logger.log(level, message, extra=extra)
