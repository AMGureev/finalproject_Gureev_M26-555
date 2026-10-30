"""Валидации сумм, UTC-время и преобразование курсов из кэша."""

import math
from datetime import datetime, timezone

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader

MIN_PASSWORD_LENGTH = 4
PASSWORD_HASH_HEX_LENGTH = 64
SALT_BYTES = 16


def utc_now():
    """Вернуть текущее время UTC с часовым поясом."""
    return datetime.now(timezone.utc)


def iso_now():
    """Вернуть ISO-метку UTC для JSON и журналов."""
    return utc_now().isoformat().replace("+00:00", "Z")


def parse_timestamp(value):
    """Прочитать ISO-дату; даты без зоны считать UTC."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def validate_number(value, *, positive=True):
    """Принять конечное число, исключая bool, NaN и бесконечности."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("'amount' должен быть положительным числом")
    number = float(value)
    if not math.isfinite(number) or (number <= 0 if positive else number < 0):
        message = "'amount' должен быть положительным числом"
        if not positive:
            message = "Баланс должен быть конечным неотрицательным числом"
        raise ValueError(message)
    return number


class RateService:
    """Читать свежий кэш, при необходимости один раз запускать обновление."""

    def __init__(self, updater=None):
        self.settings = SettingsLoader()
        self.database = DatabaseManager()
        self.updater = updater

    def _to_usd(self, code, pairs):
        """Получить цену одной единицы в USD и время измерения."""
        if code == "USD":
            return 1.0, utc_now()
        pair = pairs.get(f"{code}_USD")
        inverse = False
        if pair is None:
            pair = pairs.get(f"USD_{code}")
            inverse = True
        if not isinstance(pair, dict):
            raise ValueError("В кэше нет нужной пары")
        rate = validate_number(pair["rate"])
        return (1 / rate if inverse else rate), parse_timestamp(pair["updated_at"])

    def _read(self, from_code, to_code):
        """Вычислить прямой, обратный или кросс-курс через USD."""
        cache = self.database.read(self.settings.data_path("rates_file"), {"pairs": {}})
        pairs = cache.get("pairs", {})
        from_rate, from_time = self._to_usd(from_code, pairs)
        to_rate, to_time = self._to_usd(to_code, pairs)
        updated_at = min(from_time, to_time)
        age = (utc_now() - updated_at).total_seconds()
        if age > self.settings.get("rates_ttl_seconds") or age < 0:
            raise ValueError("Курс в кэше устарел")
        return {
            "rate": validate_number(from_rate / to_rate),
            "updated_at": updated_at.isoformat().replace("+00:00", "Z"),
        }

    def get_rate(self, from_code, to_code):
        """Вернуть курс и updated_at, не используя просроченные данные."""
        get_currency(from_code)
        get_currency(to_code)
        if from_code == to_code:
            return {"rate": 1.0, "updated_at": iso_now()}
        try:
            return self._read(from_code, to_code)
        except (KeyError, ValueError, TypeError, AttributeError):
            pass
        if self.updater is None:
            from valutatrade_hub.parser_service.updater import RatesUpdater

            updater = RatesUpdater()
        else:
            updater = self.updater
        try:
            updater.run_update()
            return self._read(from_code, to_code)
        except (
            ApiRequestError,
            KeyError,
            ValueError,
            TypeError,
            AttributeError,
        ) as error:
            raise ApiRequestError(
                f"Курс {from_code}→{to_code} недоступен или устарел. "
                "Выполните update-rates и повторите попытку позже."
            ) from error
