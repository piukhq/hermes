import json
import logging
from typing import TYPE_CHECKING, cast

from gunicorn.glogging import Logger as GLogger

if TYPE_CHECKING:
    from gunicorn.config import Config


class JSONFormatter(logging.Formatter):
    def __init__(self) -> None:
        pass

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        fmt_record = {
            "timestamp": record.created,
            "level": record.levelno,
            "levelname": record.levelname,
            "process": record.processName,
            "thread": record.threadName,
            "file": record.pathname,
            "line": record.lineno,
            "module": record.module,
            "function": record.funcName,
            "name": record.name,
        }

        if record.name == "gunicorn.access" and (val := record.args.get("{x-azure-ref}i")):
            fmt_record["x_azure_ref"] = val

        fmt_record["message"] = record.getMessage()
        return json.dumps(fmt_record)


class GunicornAccessFiltering(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if request_info := cast(str, record.args.get("r")):
            return not any(endpoint in request_info for endpoint in ("/livez", "/readyz", "/metrics"))

        return True


class CustomGunicornLogger(GLogger):
    def setup(self, cfg: "Config") -> None:
        super().setup(cfg)
        self._set_handler(self.error_log, cfg.errorlog, JSONFormatter())
        self._set_handler(self.access_log, cfg.accesslog, JSONFormatter())
        self.access_log.addFilter(GunicornAccessFiltering())
