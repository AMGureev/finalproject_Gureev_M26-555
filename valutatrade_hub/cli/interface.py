"""Парсинг команд и представление результатов без бизнес-логики."""

import argparse
import shlex
import sys

from prettytable import PrettyTable

from valutatrade_hub.core.currencies import SUPPORTED_CODES
from valutatrade_hub.core.exceptions import (
    ApiRequestError,
    CurrencyNotFoundError,
    InsufficientFundsError,
)
from valutatrade_hub.core.usecases import TradingService
from valutatrade_hub.logging_config import setup_logging


def create_parser():
    """Описать пользовательские команды и их обязательные аргументы."""
    parser = argparse.ArgumentParser(prog="project", exit_on_error=False)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("register", "login"):
        command = commands.add_parser(name)
        command.add_argument("--username", required=True)
        command.add_argument("--password", required=True)
    portfolio = commands.add_parser("show-portfolio")
    portfolio.add_argument("--base")
    for name in ("buy", "sell"):
        command = commands.add_parser(name)
        command.add_argument("--currency", required=True)
        command.add_argument("--amount", type=float, required=True)
    rate = commands.add_parser("get-rate")
    rate.add_argument("--from", dest="from_code", required=True)
    rate.add_argument("--to", dest="to_code", required=True)
    update = commands.add_parser("update-rates")
    update.add_argument("--source", choices=("coingecko", "exchangerate"))
    show = commands.add_parser("show-rates")
    show.add_argument("--currency")
    show.add_argument("--top", type=int)
    show.add_argument("--base", default="USD")
    help_command = commands.add_parser("help")
    help_command.add_argument("topic", nargs="?")
    commands.add_parser("exit")
    return parser


class CommandInterface:
    """Интерактивный интерфейс одной пользовательской сессии."""

    def __init__(self, service=None):
        self.service = service or TradingService()
        self.parser = create_parser()

    def _dispatch(self, arguments):
        """Вызвать сценарий и напечатать его результат."""
        command = arguments.command
        if command == "exit":
            print("Работа завершена")
            return False
        if command == "help":
            tokens = [arguments.topic, "--help"] if arguments.topic else ["--help"]
            self.parser.parse_args(tokens)
        elif command == "register":
            user = self.service.register(arguments.username, arguments.password)
            print(
                f"Пользователь '{user['username']}' зарегистрирован "
                f"(id={user['user_id']}). "
                f"Войдите: login --username {user['username']} --password ****"
            )
        elif command == "login":
            user = self.service.login(arguments.username, arguments.password)
            print(f"Вы вошли как '{user['username']}'")
        elif command == "show-portfolio":
            value = self.service.show_portfolio(arguments.base)
            print(
                f"Портфель пользователя '{value['username']}' (база: {value['base']}):"
            )
            if not value["wallets"]:
                print("Портфель пуст")
            else:
                table = PrettyTable(["Валюта", "Баланс", f"Стоимость, {value['base']}"])
                for wallet in value["wallets"]:
                    table.add_row(
                        [
                            wallet["currency"],
                            f"{wallet['balance']:.4f}",
                            f"{wallet['value']:,.2f}",
                        ]
                    )
                print(table)
            print(f"ИТОГО: {value['total']:,.2f} {value['base']}")
        elif command in ("buy", "sell"):
            value = getattr(self.service, command)(arguments.currency, arguments.amount)
            label = "Покупка" if command == "buy" else "Продажа"
            print(
                f"{label} выполнена: {value['amount']:.4f} {value['currency']} "
                f"по курсу {value['rate']:.2f} USD/{value['currency']}"
            )
            print(
                f"Изменения в портфеле: {value['currency']}: "
                f"было {value['before']:.4f} → стало {value['after']:.4f}"
            )
            label = (
                "Оценочная стоимость покупки"
                if command == "buy"
                else "Оценочная выручка"
            )
            print(f"{label}: {value['value']:,.2f} USD")
        elif command == "get-rate":
            value = self.service.get_rate(arguments.from_code, arguments.to_code)
            print(
                f"Курс {arguments.from_code}→{arguments.to_code}: {value['rate']:.8f} "
                f"(обновлено: {value['updated_at']})"
            )
            print(
                f"Обратный курс {arguments.to_code}→{arguments.from_code}: "
                f"{1 / value['rate']:.8f}"
            )
        elif command == "update-rates":
            value = self.service.update_rates(arguments.source)
            print(
                f"Обновлено курсов: {value['count']}. Последнее обновление: "
                f"{value['last_refresh']}"
            )
            if value["errors"]:
                print("Обновление завершено с ошибками. Подробности: logs/parser.log")
                for message in value["errors"]:
                    print(message)
        elif command == "show-rates":
            value = self.service.show_rates(
                arguments.currency, arguments.top, arguments.base
            )
            print(f"Курсы из кеша (обновлено: {value['last_refresh']}):")
            table = PrettyTable(["Пара", "Курс", "Обновлено", "Свежесть"])
            for rate in value["rates"]:
                table.add_row(
                    [
                        rate["pair"],
                        f"{rate['rate']:.8f}",
                        rate["updated_at"],
                        "устарел" if rate["stale"] else "актуален",
                    ]
                )
            print(table)
        return True

    def execute(self, tokens):
        """Обработать одну команду; ошибки не завершают интерактивный сеанс."""
        try:
            arguments = self.parser.parse_args(tokens)
            return self._dispatch(arguments)
        except SystemExit:
            return True
        except CurrencyNotFoundError as error:
            print(
                f"{error}. Поддерживаемые коды: {', '.join(SUPPORTED_CODES)}. "
                "Справка: help get-rate"
            )
        except InsufficientFundsError as error:
            print(error)
        except ApiRequestError as error:
            print(f"{error} Проверьте сеть и повторите попытку позже.")
        except (ValueError, OSError, argparse.ArgumentError) as error:
            print(f"Ошибка: {error}")
        return True

    def run(self):
        """Запустить цикл с постоянной сессией и безопасным завершением по EOF."""
        print("ValutaTrade Hub. Справка: help. Выход: exit.")
        while True:
            try:
                line = input("> ")
                tokens = shlex.split(line)
                if tokens and not self.execute(tokens):
                    break
            except ValueError as error:
                print(f"Ошибка: {error}")
            except (EOFError, KeyboardInterrupt):
                print("\nРабота завершена")
                break


def main():
    """Настроить логи, затем запустить команду или интерактивную сессию."""
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")
    try:
        setup_logging()
        interface = CommandInterface()
        if len(sys.argv) > 1:
            interface.execute(sys.argv[1:])
        else:
            interface.run()
    except (OSError, ValueError) as error:
        print(f"Ошибка запуска: {error}")


if __name__ == "__main__":
    main()
