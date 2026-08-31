"""Shared logging setup for the blob server and the load balancer.

Always logs to stdout. When LOGZIO_TOKEN is set, also ships every log line to
Logz.io over HTTPS via logzio-python-handler so the same events show up in the
Logz.io UI.
"""

import json
import logging
import os
import sys
from pathlib import Path


LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
DEFAULT_LOGZIO_SERVICE = "Artur&Tom 💪"


class CleanLogzioHandler:
    """Lazy wrapper — real base class set once logzio is imported."""

    @staticmethod
    def create(**kwargs):
        from logzio.handler import LogzioHandler

        class _Handler(LogzioHandler):
            def format_message(self, message):
                payload = super().format_message(message)
                payload.pop("path_name", None)
                payload.pop("line_number", None)
                return payload

        return _Handler(**kwargs)


def _load_dotenv() -> None:
    """Load repo-root .env into os.environ (does not override existing vars)."""

    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return

    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def configure_logging(service_name: str) -> logging.Logger:
    """
    Configure root logging once for this process.

    - Always: stdout StreamHandler (so local runs and containers still see logs).
    - When LOGZIO_TOKEN is set: also a LogzioHandler that bulk-ships JSON logs
      to the Logz.io listener. Search in Logz.io by type=LOGZIO_TYPE and the
      `service` field we attach below.
    """

    _load_dotenv()

    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    token = os.getenv("LOGZIO_TOKEN", "").strip()
    listener_url = os.getenv(
        "LOGZIO_LISTENER_URL", "https://listener.logz.io:8071"
    ).rstrip("/")
    logzio_type = os.getenv("LOGZIO_TYPE", "backend-rebase 😎")
    logzio_service = os.getenv("LOGZIO_SERVICE", DEFAULT_LOGZIO_SERVICE)
    drain_timeout = float(os.getenv("LOGZIO_DRAIN_TIMEOUT", "3"))

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.setLevel(log_level)

    stdout = logging.StreamHandler(sys.stdout)
    stdout.setFormatter(logging.Formatter(LOG_FORMAT))
    root.addHandler(stdout)

    if token:
        try:
            logzio = CleanLogzioHandler.create(
                token=token,
                logzio_type=logzio_type,
                logs_drain_timeout=drain_timeout,
                url=listener_url,
                debug=os.getenv("LOGZIO_DEBUG", "").lower() in ("1", "true", "yes"),
                backup_logs=True,
            )
        except ImportError as exc:
            raise RuntimeError(
                "LOGZIO_TOKEN is set but logzio-python-handler is not installed. "
                "Add it to requirements.txt and pip install."
            ) from exc

        # Extra fields become searchable columns in Logz.io. The formatter JSON
        # is merged into every shipped record by LogzioHandler.
        logzio.setLevel(log_level)
        logzio.setFormatter(
            logging.Formatter(
                json.dumps({"service": logzio_service}),
                validate=False,
            )
        )
        root.addHandler(logzio)
        logging.getLogger("logging_setup").info(
            "Logz.io shipping enabled (type=%s listener=%s service=%s)",
            logzio_type,
            listener_url,
            logzio_service,
        )
    else:
        logging.getLogger("logging_setup").info(
            "Logz.io shipping disabled (set LOGZIO_TOKEN to enable); "
            "logging to stdout only"
        )

    # httpx INFO duplicates our own forward/route lines.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    return logging.getLogger(service_name)
