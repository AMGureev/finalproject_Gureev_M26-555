"""Доменные исключения, отображаемые командным интерфейсом."""


class InsufficientFundsError(Exception):
    """Снятие превышает доступный остаток кошелька."""

    def __init__(self, available, required, code):
        self.available = available
        self.required = required
        self.code = code
        super().__init__(
            f"Недостаточно средств: доступно {available:.4f} {code}, "
            f"требуется {required:.4f} {code}"
        )


class CurrencyNotFoundError(Exception):
    """Валюта отсутствует в реестре поддерживаемых кодов."""

    def __init__(self, code):
        self.code = code
        super().__init__(f"Неизвестная валюта '{code}'")


class ApiRequestError(Exception):
    """Не удалось получить пригодные для использования курсы."""

    def __init__(self, reason):
        super().__init__(f"Ошибка при обращении к внешнему API: {reason}")
