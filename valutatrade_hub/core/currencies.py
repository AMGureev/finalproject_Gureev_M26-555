"""Иерархия фиатных и криптовалют и фабрика валют."""

from abc import ABC, abstractmethod

from valutatrade_hub.core.exceptions import CurrencyNotFoundError

FIAT_INFO = {
    "USD": ("US Dollar", "United States"),
    "EUR": ("Euro", "Eurozone"),
    "GBP": ("Pound Sterling", "United Kingdom"),
    "RUB": ("Russian Ruble", "Russia"),
}
CRYPTO_INFO = {
    "BTC": ("Bitcoin", "SHA-256", 0.0),
    "ETH": ("Ethereum", "Proof of Stake", 0.0),
    "SOL": ("Solana", "Proof of History", 0.0),
}
SUPPORTED_CODES = tuple(FIAT_INFO) + tuple(CRYPTO_INFO)
CODE_MIN_LENGTH = 2
CODE_MAX_LENGTH = 5


def validate_code(code):
    """Проверить верхний регистр и длину кода без пробелов."""
    if (
        not isinstance(code, str)
        or not CODE_MIN_LENGTH <= len(code) <= CODE_MAX_LENGTH
        or not code.isascii()
        or not code.isalpha()
        or code != code.upper()
    ):
        raise ValueError("Код валюты: 2–5 латинских букв в верхнем регистре")
    return code


class Currency(ABC):
    """Абстрактная валюта с валидными именем и кодом."""

    def __init__(self, name, code):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Название валюты не может быть пустым")
        self.name = name.strip()
        self.code = validate_code(code)

    @abstractmethod
    def get_display_info(self):
        """Вернуть описание валюты для интерфейса и журналов."""


class FiatCurrency(Currency):
    """Фиатная валюта со страной или зоной эмиссии."""

    def __init__(self, name, code, issuing_country):
        super().__init__(name, code)
        self.issuing_country = issuing_country

    def get_display_info(self):
        """Показать имя, код и эмитента валюты."""
        return f"[FIAT] {self.code} — {self.name} (Issuing: {self.issuing_country})"


class CryptoCurrency(Currency):
    """Криптовалюта с алгоритмом и последней известной капитализацией."""

    def __init__(self, name, code, algorithm, market_cap):
        super().__init__(name, code)
        self.algorithm = algorithm
        self.market_cap = market_cap

    def get_display_info(self):
        """Показать алгоритм; нулевая капитализация означает отсутствие данных."""
        capitalization = f"{self.market_cap:.2e}" if self.market_cap else "n/a"
        return (
            f"[CRYPTO] {self.code} — {self.name} "
            f"(Algo: {self.algorithm}, MCAP: {capitalization})"
        )


def get_currency(code):
    """Создать валюту из реестра или выбросить CurrencyNotFoundError."""
    validate_code(code)
    if code in FIAT_INFO:
        name, country = FIAT_INFO[code]
        return FiatCurrency(name, code, country)
    if code in CRYPTO_INFO:
        name, algorithm, capitalization = CRYPTO_INFO[code]
        return CryptoCurrency(name, code, algorithm, capitalization)
    raise CurrencyNotFoundError(code)
