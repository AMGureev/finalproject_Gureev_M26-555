"""Унифицированные клиенты CoinGecko и ExchangeRate-API."""

import time
from abc import ABC, abstractmethod

import requests

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.utils import validate_number
from valutatrade_hub.parser_service.config import HTTP_ERRORS, ParserConfig


class BaseApiClient(ABC):
    """Общий контракт получения пар вида CODE_USD и метаданных измерений."""

    source = ""
    source_key = ""

    def __init__(self, config=None):
        self.config = config or ParserConfig()
        self.metadata = {}

    def _get(self, url, *, params=None, headers=None):
        """Выполнить GET с таймаутом и скрыть URL с ключом из ошибок."""
        started = time.monotonic()
        try:
            response = requests.get(
                url, params=params, headers=headers, timeout=self.config.REQUEST_TIMEOUT
            )
            if response.status_code != requests.codes.ok:
                reason = HTTP_ERRORS.get(response.status_code, "сервис недоступен")
                raise ApiRequestError(
                    f"{self.source}: HTTP {response.status_code}, {reason}"
                )
            value = response.json()
            if not isinstance(value, dict):
                raise ApiRequestError(f"{self.source}: ожидался JSON-объект")
            self._response_meta = {
                "request_ms": round((time.monotonic() - started) * 1000),
                "status_code": response.status_code,
            }
            if response.headers.get("ETag"):
                self._response_meta["etag"] = response.headers["ETag"]
            return value
        except requests.exceptions.JSONDecodeError as error:
            raise ApiRequestError(f"{self.source}: некорректный JSON") from error
        except requests.exceptions.Timeout as error:
            raise ApiRequestError(
                f"{self.source}: истекло время ожидания ответа"
            ) from error
        except requests.exceptions.RequestException as error:
            raise ApiRequestError(f"{self.source}: сетевая ошибка") from error
        except ValueError as error:
            raise ApiRequestError(f"{self.source}: некорректный JSON") from error

    @abstractmethod
    def fetch_rates(self) -> dict:
        """Вернуть положительные конечные курсы в едином формате."""


class CoinGeckoClient(BaseApiClient):
    """Получение криптовалют по CoinGecko ID, а не тикерам."""

    source = "CoinGecko"
    source_key = "coingecko"

    def fetch_rates(self) -> dict:
        """Получить цену каждой настроенной криптовалюты в базовой валюте."""
        mapping = self.config.CRYPTO_ID_MAP
        headers = {}
        if self.config.COINGECKO_API_KEY:
            headers["x-cg-demo-api-key"] = self.config.COINGECKO_API_KEY
        value = self._get(
            self.config.COINGECKO_URL,
            params={
                "ids": ",".join(
                    mapping[code] for code in self.config.CRYPTO_CURRENCIES
                ),
                "vs_currencies": self.config.BASE_CURRENCY.lower(),
            },
            headers=headers,
        )
        rates = {}
        metadata = {}
        try:
            for code in self.config.CRYPTO_CURRENCIES:
                raw_id = mapping[code]
                pair = f"{code}_{self.config.BASE_CURRENCY}"
                rates[pair] = validate_number(
                    value[raw_id][self.config.BASE_CURRENCY.lower()]
                )
                metadata[pair] = {**self._response_meta, "raw_id": raw_id}
        except (KeyError, TypeError, ValueError) as error:
            raise ApiRequestError(
                "CoinGecko: отсутствующие или некорректные курсы"
            ) from error
        self.metadata = metadata
        return rates


class ExchangeRateApiClient(BaseApiClient):
    """Получение и обращение фиатных курсов из ExchangeRate-API."""

    source = "ExchangeRate-API"
    source_key = "exchangerate"

    def fetch_rates(self) -> dict:
        """Перевести ответ USD→CODE в единый формат CODE→USD."""
        if not self.config.EXCHANGERATE_API_KEY:
            raise ApiRequestError("Задайте EXCHANGERATE_API_KEY в переменной окружения")
        url = (
            f"{self.config.EXCHANGERATE_API_URL}/"
            f"{self.config.EXCHANGERATE_API_KEY}/latest/{self.config.BASE_CURRENCY}"
        )
        value = self._get(url)
        if value.get("result") != "success":
            reason = value.get("error-type", "некорректный ответ")
            raise ApiRequestError(f"ExchangeRate-API: {reason}")
        if value.get("base_code") != self.config.BASE_CURRENCY:
            raise ApiRequestError("ExchangeRate-API: неверная базовая валюта ответа")
        try:
            raw_rates = value.get("conversion_rates", value.get("rates"))
            rates = {
                f"{code}_{self.config.BASE_CURRENCY}": validate_number(
                    1 / validate_number(raw_rates[code])
                )
                for code in self.config.FIAT_CURRENCIES
            }
        except (KeyError, TypeError, ValueError, ZeroDivisionError) as error:
            raise ApiRequestError("ExchangeRate-API: некорректные курсы") from error
        self.metadata = {pair: self._response_meta.copy() for pair in rates}
        return rates
