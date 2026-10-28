"""JSON- или текстовые журналы с ротацией по размеру."""

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from valutatrade_hub.core.utils import iso_now
from valutatrade_hub.infra.settings import SettingsLoader


class JsonFormatter(logging.Formatter):
    """Форматировать одну запись в JSON с ISO-временем UTC."""

    def format(self, record):
        """Сохранить структурированные поля действия или текст парсера."""
        value = {"timestamp": iso_now(), "level": record.levelname}
        value.update(getattr(record, "action_data", {"message": record.getMessage()}))
        return json.dumps(value, ensure_ascii=False, default=str, allow_nan=False)


def setup_logging():
    """Подключить отдельные ротируемые журналы действий и обновления курсов."""
    settings = SettingsLoader()
    log_dir = Path(settings.get("log_dir"))
    log_dir.mkdir(parents=True, exist_ok=True)
    for name, filename in (("actions", "actions.log"), ("parser", "parser.log")):
        logger = logging.getLogger(f"valutatrade.{name}")
        path = (log_dir / filename).resolve()
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
        handler = RotatingFileHandler(
            path,
            maxBytes=settings.get("log_max_bytes"),
            backupCount=settings.get("log_backup_count"),
            encoding="utf-8",
        )
        formatter = JsonFormatter()
        if settings.get("log_format") == "text":
            formatter = logging.Formatter("%(levelname)s %(asctime)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(settings.get("log_level"))
        logger.propagate = False
