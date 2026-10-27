"""Единая конфигурация приложения из pyproject.toml и окружения."""

import os
import tomllib
from pathlib import Path
from threading import RLock

DEFAULTS = {
    "data_dir": "data",
    "users_file": "users.json",
    "portfolios_file": "portfolios.json",
    "rates_file": "rates.json",
    "history_file": "exchange_rates.json",
    "rates_ttl_seconds": 300,
    "default_base_currency": "USD",
    "log_dir": "logs",
    "log_format": "json",
    "log_level": "INFO",
    "log_max_bytes": 1048576,
    "log_backup_count": 3,
    "update_interval": 300,
}


class SettingsLoader:
    """Загрузить настройки один раз; get читает их, reload обновляет."""

    _instance = None
    _lock = RLock()

    def __new__(cls):
        # __new__ явно гарантирует один экземпляр без дополнительного метакласса.
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance.reload()
                cls._instance = instance
            return cls._instance

    def get(self, key, default=None):
        """Вернуть значение настройки или указанное значение по умолчанию."""
        return self._settings.get(key, default)

    def reload(self):
        """Перечитать настройки текущей рабочей папки и переменные окружения."""
        settings = DEFAULTS.copy()
        config = Path("pyproject.toml")
        if config.is_file():
            with config.open("rb") as stream:
                settings.update(
                    tomllib.load(stream).get("tool", {}).get("valutatrade", {})
                )
        for key in ("data_dir", "log_dir"):
            settings[key] = os.getenv(f"VALUTATRADE_{key.upper()}", settings[key])
        for key in ("rates_ttl_seconds", "update_interval", "log_max_bytes"):
            value = settings[key]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value <= 0
            ):
                raise ValueError(f"Настройка {key} должна быть положительным числом")
        if settings["log_format"] not in ("json", "text"):
            raise ValueError("log_format должен быть json или text")
        self._settings = settings

    def data_path(self, key):
        """Построить путь к одному из файлов данных."""
        return Path(self.get("data_dir")) / self.get(key)
