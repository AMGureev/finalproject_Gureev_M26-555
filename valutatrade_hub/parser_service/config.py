"""Централизованная конфигурация источников и файлов Parser Service."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from valutatrade_hub.infra.settings import SettingsLoader

CRYPTO_ID_MAP = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}
HTTP_ERRORS = {
    401: "неверный API-ключ",
    403: "доступ запрещён",
    429: "превышен лимит запросов; повторите позже",
}


@dataclass
class ParserConfig:
    """Параметры запросов; ключи читаются из окружения при создании."""

    EXCHANGERATE_API_KEY: str = field(
        default_factory=lambda: os.getenv("EXCHANGERATE_API_KEY", "")
    )
    COINGECKO_API_KEY: str = field(
        default_factory=lambda: os.getenv("COINGECKO_API_KEY", "")
    )
    COINGECKO_URL: str = "https://api.coingecko.com/api/v3/simple/price"
    EXCHANGERATE_API_URL: str = "https://v6.exchangerate-api.com/v6"
    BASE_CURRENCY: str = "USD"
    FIAT_CURRENCIES: tuple = ("EUR", "GBP", "RUB")
    CRYPTO_CURRENCIES: tuple = ("BTC", "ETH", "SOL")
    CRYPTO_ID_MAP: dict = field(default_factory=lambda: CRYPTO_ID_MAP.copy())
    REQUEST_TIMEOUT: int = 10
    RATES_FILE_PATH: Path = field(
        default_factory=lambda: SettingsLoader().data_path("rates_file")
    )
    HISTORY_FILE_PATH: Path = field(
        default_factory=lambda: SettingsLoader().data_path("history_file")
    )
