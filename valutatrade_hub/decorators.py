"""Прозрачное логирование доменных операций без подавления исключений."""

import functools
import inspect
import json
import logging
import math


def log_action(action=None, *, verbose=False):
    """Записать действие, параметры и OK/ERROR; verbose добавляет изменения."""
    if callable(action):
        return log_action(verbose=verbose)(action)

    def decorate(function):
        """Обернуть метод сценария, сохранив его имя и docstring."""

        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            """Вызвать операцию, зафиксировать результат и пробросить ошибку."""
            arguments = inspect.signature(function).bind(*args, **kwargs).arguments
            service = arguments.get("self")
            user = getattr(service, "current_user", None)
            amount = arguments.get("amount")
            if isinstance(amount, float) and not math.isfinite(amount):
                amount = str(amount)
            context = {
                "action": action or function.__name__.upper(),
                "username": user.username if user else None,
                "user_id": user.user_id if user else None,
                "currency_code": arguments.get("currency_code"),
                "amount": amount,
                "base": "USD",
                "rate": None,
            }
            logger = logging.getLogger("valutatrade.actions")
            try:
                result = function(*args, **kwargs)
                values = result if isinstance(result, dict) else {}
                context.update(result="OK", rate=values.get("rate"))
                if verbose:
                    context.update(
                        before=values.get("before"), after=values.get("after")
                    )
            except Exception as error:
                context.update(
                    result="ERROR",
                    error_type=type(error).__name__,
                    error_message=str(error),
                )
                logger.info(
                    json.dumps(context, ensure_ascii=False, default=str),
                    extra={"action_data": context},
                )
                raise
            logger.info(
                json.dumps(context, ensure_ascii=False, default=str),
                extra={"action_data": context},
            )
            return result

        return wrapper

    return decorate
