"""Регистрация, сессия, сделки и запросы к валютному портфелю."""

from valutatrade_hub.core.currencies import CRYPTO_INFO, get_currency
from valutatrade_hub.core.models import Portfolio, User
from valutatrade_hub.core.utils import (
    RateService,
    parse_timestamp,
    utc_now,
    validate_number,
)
from valutatrade_hub.decorators import log_action
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.infra.settings import SettingsLoader


class TradingService:
    """Сценарии приложения; текущая сессия хранится только в памяти процесса."""

    def __init__(self, database=None, rate_service=None):
        self.database = database or DatabaseManager()
        self.settings = SettingsLoader()
        self.rates = rate_service or RateService()
        self.current_user = None

    def register(self, username, password):
        """Проверить уникальность имени, сохранить пользователя и пустой портфель."""
        if not isinstance(username, str) or not username.strip():
            raise ValueError("Имя пользователя не может быть пустым")
        username = username.strip()

        def add_user(users):
            """Зарегистрировать пользователя под блокировкой хранилища."""
            if any(user["username"] == username for user in users):
                raise ValueError(f"Имя пользователя '{username}' уже занято")
            user_id = max((value["user_id"] for value in users), default=0) + 1
            user = User.create(user_id, username, password)

            def add_portfolio(portfolios):
                """Создать ровно один пустой портфель нового пользователя."""
                portfolios.append({"user_id": user_id, "wallets": {}})

            self.database.update(
                self.settings.data_path("portfolios_file"), add_portfolio, []
            )
            users.append(user.to_dict())
            return user.get_user_info()

        return self.database.update(self.settings.data_path("users_file"), add_user, [])

    def login(self, username, password):
        """Войти после проверки пароля; ошибочный вход сбрасывает прежнюю сессию."""
        self.current_user = None
        for value in self.database.load_users():
            if value["username"] == username:
                user = User.from_dict(value)
                if not user.verify_password(password):
                    raise ValueError("Неверный пароль")
                self.current_user = user
                return user.get_user_info()
        raise ValueError(f"Пользователь '{username}' не найден")

    def _require_user(self):
        """Запретить операции с чужим или неавторизованным портфелем."""
        if self.current_user is None:
            raise ValueError("Сначала выполните login")
        return self.current_user

    def _portfolio(self, records):
        """Восстановить портфель текущего пользователя из списка записей."""
        user = self._require_user()
        for value in records:
            if value["user_id"] == user.user_id:
                return Portfolio(
                    user.user_id, value["wallets"], user, self.rates.get_rate
                )
        raise ValueError("Портфель пользователя не найден")

    def show_portfolio(self, base_currency=None):
        """Вернуть остатки, оценки и итоговую стоимость для представления в CLI."""
        self._require_user()
        base = base_currency or self.settings.get("default_base_currency")
        get_currency(base)
        portfolio = self._portfolio(self.database.load_portfolios())
        rows = []
        for code, wallet in sorted(portfolio.wallets.items()):
            rate = self.rates.get_rate(code, base)["rate"] if wallet.balance else 0
            rows.append(
                {
                    "currency": code,
                    "balance": wallet.balance,
                    "value": wallet.balance * rate,
                }
            )
        return {
            "username": self.current_user.username,
            "base": base,
            "wallets": rows,
            "total": sum(row["value"] for row in rows),
        }

    def _trade(self, currency_code, amount, *, selling):
        """Изменить один кошелёк после всех проверок и сохранить новый портфель."""
        self._require_user()
        get_currency(currency_code)
        amount = validate_number(amount)
        rate = self.rates.get_rate(currency_code, "USD")["rate"]
        validate_number(rate * amount)

        def change(portfolios):
            """Изменить копию модели; записать её только после успешной операции."""
            portfolio = self._portfolio(portfolios)
            wallet = (
                portfolio.get_wallet(currency_code)
                if selling
                else portfolio.add_currency(currency_code)
            )
            before = wallet.balance
            if selling:
                wallet.withdraw(amount)
            else:
                wallet.deposit(amount)
            for index, value in enumerate(portfolios):
                if value["user_id"] == self.current_user.user_id:
                    portfolios[index] = portfolio.to_dict()
                    break
            return {
                "currency": currency_code,
                "amount": amount,
                "rate": rate,
                "base": "USD",
                "before": before,
                "after": wallet.balance,
                "value": amount * rate,
            }

        return self.database.update(
            self.settings.data_path("portfolios_file"), change, []
        )

    @log_action("BUY", verbose=True)
    def buy(self, currency_code, amount):
        """Добавить валюту в учебный портфель и вычислить её оценку в USD."""
        return self._trade(currency_code, amount, selling=False)

    @log_action("SELL", verbose=True)
    def sell(self, currency_code, amount):
        """Списать валюту при достаточном остатке и вычислить оценочную выручку."""
        return self._trade(currency_code, amount, selling=True)

    def get_rate(self, from_code, to_code):
        """Получить свежий прямой, обратный или кросс-курс."""
        return self.rates.get_rate(from_code, to_code)

    def update_rates(self, source=None):
        """Запустить Parser Service без требования входа в кошелёк."""
        from valutatrade_hub.parser_service.updater import RatesUpdater

        return RatesUpdater().run_update(source)

    def show_rates(self, currency=None, top=None, base="USD"):
        """Отфильтровать локальный кэш и показать N самых дорогих криптовалют."""
        get_currency(base)
        if currency is not None:
            get_currency(currency)
        if top is not None and (
            isinstance(top, bool) or not isinstance(top, int) or top <= 0
        ):
            raise ValueError("--top должен быть положительным целым числом")
        cache = self.database.read(self.settings.data_path("rates_file"), {"pairs": {}})
        pairs = cache.get("pairs", {})
        if not pairs:
            raise ValueError(
                "Локальный кеш курсов пуст. "
                "Выполните 'update-rates', чтобы загрузить данные."
            )
        usd_rates = {"USD": 1.0}
        timestamps = {}
        for pair, value in pairs.items():
            from_code, to_code = pair.split("_")
            if to_code == "USD":
                usd_rates[from_code] = validate_number(value["rate"])
                timestamps[from_code] = value["updated_at"]
        if base not in usd_rates:
            raise ValueError(f"Курс для '{base}' не найден в кеше.")
        result = []
        for code, timestamp in sorted(timestamps.items()):
            if currency is not None and code != currency:
                continue
            if top is not None and code not in CRYPTO_INFO:
                continue
            times = [parse_timestamp(timestamp)]
            if base in timestamps:
                times.append(parse_timestamp(timestamps[base]))
            measured_at = min(times)
            age = (utc_now() - measured_at).total_seconds()
            result.append(
                {
                    "pair": f"{code}_{base}",
                    "rate": usd_rates[code] / usd_rates[base],
                    "updated_at": measured_at.isoformat(),
                    "stale": age > self.settings.get("rates_ttl_seconds") or age < 0,
                }
            )
        if not result and currency is not None:
            raise ValueError(f"Курс для '{currency}' не найден в кеше.")
        if top is not None:
            result.sort(key=lambda value: value["rate"], reverse=True)
            result = result[:top]
        return {"rates": result, "last_refresh": cache.get("last_refresh")}
