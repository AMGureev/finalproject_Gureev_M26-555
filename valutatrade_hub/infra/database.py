"""Чтение, безопасное изменение и атомарная запись JSON-файлов."""

import copy
import json
import os
import tempfile
from pathlib import Path
from threading import RLock

from valutatrade_hub.infra.settings import SettingsLoader


class DatabaseManager:
    """Единый менеджер JSON-хранилища с блокировкой операций в процессе."""

    _instance = None
    _lock = RLock()

    def __new__(cls):
        # __new__ сохраняет простой интерфейс конструктора и единственный экземпляр.
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def read(self, path, default):
        """Прочитать JSON; для отсутствующего файла вернуть независимый default."""
        with self._lock:
            try:
                with Path(path).open(encoding="utf-8") as stream:
                    return json.load(stream)
            except FileNotFoundError:
                return copy.deepcopy(default)
            except json.JSONDecodeError as error:
                raise ValueError(f"Повреждён JSON-файл {path}") from error

    def write(self, path, value):
        """Сохранить JSON через временный файл в том же каталоге и os.replace."""
        path = Path(path)
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=path.parent,
                    prefix=path.name + ".",
                    suffix=".tmp",
                    delete=False,
                ) as stream:
                    temporary = Path(stream.name)
                    json.dump(
                        value, stream, ensure_ascii=False, indent=2, allow_nan=False
                    )
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                if temporary is not None and temporary.exists():
                    temporary.unlink()

    def update(self, path, transform, default):
        """Выполнить чтение, преобразование и запись под одной блокировкой."""
        with self._lock:
            value = self.read(path, default)
            result = transform(value)
            self.write(path, value)
            return result

    def load_users(self):
        """Прочитать список пользователей."""
        return self.read(SettingsLoader().data_path("users_file"), [])

    def load_portfolios(self):
        """Прочитать список портфелей."""
        return self.read(SettingsLoader().data_path("portfolios_file"), [])
