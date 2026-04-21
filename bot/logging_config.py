

import logging
import logging.handlers
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


class JSONFormatter(logging.Formatter):
    """Formats log records as JSON lines for structured, machine-readable log files."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            log_obj.update(record.extra)
        return json.dumps(log_obj)


class ColoredConsoleFormatter(logging.Formatter):
    """Adds ANSI color codes to console log output for readability."""

    COLORS = {
        "DEBUG":    "\033[36m",   # Cyan
        "INFO":     "\033[32m",   # Green
        "WARNING":  "\033[33m",   # Yellow
        "ERROR":    "\033[31m",   # Red
        "CRITICAL": "\033[35m",   # Magenta
    }
    RESET = "\033[0m"
    DIM   = "\033[2m"
    BOLD  = "\033[1m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        level_tag = f"{color}{self.BOLD}[{record.levelname:<8}]{self.RESET}"
        time_tag  = f"{self.DIM}{ts}{self.RESET}"
        name_tag  = f"{self.DIM}{record.name}{self.RESET}"
        msg = record.getMessage()
        line = f"{time_tag}  {level_tag}  {name_tag}  {msg}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def setup_logging(
    log_dir: str = "logs",
    log_file: str = "trading_bot.log",
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
) -> None:
    """
    Configure root logger with:
      - Rotating JSON file handler  → logs/<log_file>
      - Colored console handler     → stdout
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # ── File handler (JSON, rotating, 5 MB × 3 backups) ──────────────────────
    fh = logging.handlers.RotatingFileHandler(
        filename=log_path / log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(file_level)
    fh.setFormatter(JSONFormatter())

    # ── Console handler (colored) ────────────────────────────────────────────
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(console_level)
    ch.setFormatter(ColoredConsoleFormatter())

    root.addHandler(fh)
    root.addHandler(ch)

    # Silence overly verbose third-party loggers
    for noisy in ("urllib3", "requests", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
