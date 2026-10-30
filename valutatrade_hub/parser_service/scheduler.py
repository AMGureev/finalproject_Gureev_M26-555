"""Отдельный процесс периодического обновления курсов."""

import time

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.infra.settings import SettingsLoader
from valutatrade_hub.logging_config import setup_logging
from valutatrade_hub.parser_service.updater import RatesUpdater


def main():
    """Обновлять курсы через настроенный интервал до остановки процесса."""
    setup_logging()
    updater = RatesUpdater()
    try:
        while True:
            try:
                result = updater.run_update()
                print(f"Обновлено курсов: {result['count']}")
            except (ApiRequestError, OSError, ValueError) as error:
                updater.logger.error("Update failed: %s", error)
            time.sleep(SettingsLoader().get("update_interval"))
    except KeyboardInterrupt:
        print("Обновление курсов остановлено")


if __name__ == "__main__":
    main()
