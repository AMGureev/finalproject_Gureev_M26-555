"""Модели пользователя, кошелька и валютного портфеля."""

import hashlib
import hmac
import secrets
from datetime import datetime

from valutatrade_hub.core.currencies import get_currency
from valutatrade_hub.core.exceptions import InsufficientFundsError
from valutatrade_hub.core.utils import (
    MIN_PASSWORD_LENGTH,
    PASSWORD_HASH_HEX_LENGTH,
    SALT_BYTES,
    RateService,
    parse_timestamp,
    utc_now,
    validate_number,
)


class User:
    """Пользователь с солью, односторонним хешем и ISO-датой регистрации."""

    def __init__(self, user_id, username, hashed_password, salt, registration_date):
        if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
            raise ValueError("user_id должен быть положительным целым числом")
        if not isinstance(salt, str) or not salt:
            raise ValueError("Соль не может быть пустой")
        if (
            not isinstance(hashed_password, str)
            or len(hashed_password) != PASSWORD_HASH_HEX_LENGTH
        ):
            raise ValueError("Некорректный SHA-256 хеш")
        try:
            bytes.fromhex(hashed_password)
        except ValueError as error:
            raise ValueError("Некорректный SHA-256 хеш") from error
        self._user_id = user_id
        self.username = username
        self._hashed_password = hashed_password
        self._salt = salt
        date = registration_date
        self._registration_date = (
            parse_timestamp(date) if isinstance(date, str) else date
        )
        if not isinstance(self._registration_date, datetime):
            raise ValueError("Некорректная дата регистрации")

    @classmethod
    def create(cls, user_id, username, password):
        """Создать пользователя с новой случайной солью и текущей датой."""
        cls._check_password(password)
        salt = secrets.token_hex(SALT_BYTES)
        return cls(user_id, username, cls._hash(password, salt), salt, utc_now())

    @staticmethod
    def _hash(password, salt):
        """Вычислить требуемый заданием SHA-256 от пароля и соли."""
        return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

    @staticmethod
    def _check_password(password):
        """Проверить тип и минимальную длину нового пароля."""
        if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError("Пароль должен быть не короче 4 символов")

    @property
    def user_id(self):
        """Вернуть неизменяемый идентификатор пользователя."""
        return self._user_id

    @property
    def username(self):
        """Вернуть имя пользователя."""
        return self._username

    @username.setter
    def username(self, value):
        """Установить непустое имя без внешних пробелов."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        self._username = value.strip()

    @property
    def hashed_password(self):
        """Вернуть хеш для сохранения в хранилище."""
        return self._hashed_password

    @property
    def salt(self):
        """Вернуть индивидуальную соль пользователя."""
        return self._salt

    @property
    def registration_date(self):
        """Вернуть дату регистрации."""
        return self._registration_date

    def get_user_info(self):
        """Вернуть информацию для UI без пароля, хеша и соли."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "registration_date": self.registration_date.isoformat(),
        }

    def change_password(self, new_password):
        """Проверить новый пароль и обновить его соль и хеш."""
        self._check_password(new_password)
        self._salt = secrets.token_hex(SALT_BYTES)
        self._hashed_password = self._hash(new_password, self.salt)

    def verify_password(self, password):
        """Сравнить хеш введённого пароля с сохранённым."""
        return isinstance(password, str) and hmac.compare_digest(
            self._hash(password, self.salt), self.hashed_password
        )

    def to_dict(self):
        """Сериализовать пользователя для users.json без открытого пароля."""
        return {
            **self.get_user_info(),
            "hashed_password": self.hashed_password,
            "salt": self.salt,
        }

    @classmethod
    def from_dict(cls, value):
        """Восстановить пользователя из JSON-записи."""
        return cls(**value)


class Wallet:
    """Кошелёк одной валюты с конечным неотрицательным балансом."""

    def __init__(self, currency_code, balance=0.0):
        self.currency_code = get_currency(currency_code).code
        self.balance = balance

    @property
    def balance(self):
        """Вернуть текущий баланс."""
        return self._balance

    @balance.setter
    def balance(self, value):
        """Запретить отрицательные и нечисловые значения баланса."""
        self._balance = validate_number(value, positive=False)

    def deposit(self, amount):
        """Увеличить баланс на положительную сумму."""
        self.balance = self.balance + validate_number(amount)

    def withdraw(self, amount):
        """Снять положительную сумму, проверив доступный остаток."""
        amount = validate_number(amount)
        if amount > self.balance:
            raise InsufficientFundsError(self.balance, amount, self.currency_code)
        self.balance = self.balance - amount

    def get_balance_info(self):
        """Вернуть читаемое представление остатка."""
        return f"{self.currency_code}: {self.balance:.4f}"


class Portfolio:
    """Кошельки одного пользователя и их стоимость по текущим курсам."""

    def __init__(self, user_id, wallets=None, user=None, rate_provider=None):
        self._user_id = user_id
        self._user = user
        self._wallets = {}
        self._rate_provider = rate_provider or RateService().get_rate
        for code, wallet in (wallets or {}).items():
            if isinstance(wallet, dict):
                wallet = Wallet(code, wallet["balance"])
            if not isinstance(wallet, Wallet) or wallet.currency_code != code:
                raise ValueError("Код кошелька не соответствует ключу портфеля")
            self._wallets[code] = wallet
        if user is not None and user.user_id != user_id:
            raise ValueError("Владелец портфеля не соответствует user_id")

    @property
    def user(self):
        """Вернуть владельца портфеля без возможности перезаписать свойство."""
        if self._user is None:
            from valutatrade_hub.infra.database import DatabaseManager

            for value in DatabaseManager().load_users():
                if value["user_id"] == self._user_id:
                    self._user = User.from_dict(value)
                    break
            if self._user is None:
                raise ValueError("Пользователь портфеля не найден")
        return self._user

    @property
    def wallets(self):
        """Вернуть копию словаря кошельков."""
        return self._wallets.copy()

    def add_currency(self, currency_code):
        """Создать кошелёк один раз или вернуть уже существующий."""
        get_currency(currency_code)
        if currency_code not in self._wallets:
            self._wallets[currency_code] = Wallet(currency_code)
        return self._wallets[currency_code]

    def get_wallet(self, currency_code):
        """Вернуть кошелёк либо сообщить, как его создать."""
        get_currency(currency_code)
        if currency_code not in self._wallets:
            raise ValueError(
                f"У вас нет кошелька '{currency_code}'. Добавьте валюту: "
                "она создаётся автоматически при первой покупке."
            )
        return self._wallets[currency_code]

    def get_total_value(self, base_currency="USD"):
        """Посчитать стоимость всех ненулевых остатков в базовой валюте."""
        get_currency(base_currency)
        return sum(
            wallet.balance * self._rate_provider(code, base_currency)["rate"]
            for code, wallet in self._wallets.items()
            if wallet.balance
        )

    def to_dict(self):
        """Сериализовать кошельки в формат portfolios.json."""
        return {
            "user_id": self._user_id,
            "wallets": {
                code: {"balance": wallet.balance}
                for code, wallet in self._wallets.items()
            },
        }
