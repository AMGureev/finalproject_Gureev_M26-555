# ValutaTrade Hub

Учебный валютный кошелёк на Python 3.12: регистрация пользователей,
управление виртуальным портфелем, покупка и продажа фиатных и криптовалют.
Core Service отвечает за пользователей и операции. Parser Service получает
курсы CoinGecko и ExchangeRate-API, сохраняет актуальный снимок и историю.

## Установка и запуск

Нужны Python 3.12 и [uv](https://docs.astral.sh/uv/getting-started/installation/).

```console
git clone https://github.com/AMGureev/finalproject_Gureev_M26-555.git
cd finalproject_Gureev_M26-555
uv sync --locked
uv run project
```

Другой способ запуска из корня: `uv run python main.py`.
Команды вводятся в одном интерактивном сеансе: сессия входа хранится в памяти.
`help` показывает список команд, `help buy` — аргументы покупки,
`exit`, Ctrl+C или конец ввода завершают приложение.

При установленном GNU Make:

```console
make install
make run
make lint
make build
```

Цели выполняют `uv sync --locked`, `uv run project`, `uv run ruff check .`
и `uv build`. Версии зависимостей закреплены в `uv.lock`, Ruff — зависимость
разработки. `prettytable` используется для таблиц, `requests` — для HTTP.

## Parser Service и ключ API

Получите бесплатный ключ [ExchangeRate-API](https://app.exchangerate-api.com/sign-up)
и подтвердите почту. Ключ задаётся переменной окружения до запуска приложения.

PowerShell:

```powershell
$env:EXCHANGERATE_API_KEY = "ваш_ключ"
uv run project
```

Bash:

```bash
export EXCHANGERATE_API_KEY="ваш_ключ"
uv run project
```

Ключ не записывается в исходники, JSON с данными и журналы. Приложение не читает
`.env` автоматически. При необходимости CoinGecko Demo-ключ можно передать
через `COINGECKO_API_KEY`; публичный запрос выполняется и без него.

В интерактивном сеансе:

```text
update-rates
update-rates --source coingecko
update-rates --source exchangerate
show-rates
show-rates --currency RUB
show-rates --top 2
show-rates --base EUR
```

Без параметра `--source` опрашиваются оба источника. Ошибка одного источника
не мешает сохранить ответ другого, прежние пары остаются в кэше.
Если оба недоступны, выводится ошибка, сохранённые курсы не заменяются.
`--top` выбирает самые дорогие криптовалюты, а не фиатные валюты.

Для отдельного ручного обновления: `uv run project update-rates`.
Для периодического обновления отдельным процессом:

```console
uv run python -m valutatrade_hub.parser_service.scheduler
```

Период задаётся `update_interval` в секции `[tool.valutatrade]` файла
`pyproject.toml` (по умолчанию 300 секунд). Остановка — Ctrl+C.

CoinGecko использует ID `bitcoin`, `ethereum`, `solana` и возвращает цены
BTC, ETH, SOL в USD. ExchangeRate-API возвращает количество EUR, GBP, RUB
за USD в поле `conversion_rates`: при сохранении курс обращается,
чтобы все пары имели вид `CODE_USD`.
Поддерживается также поле `rates` из примера задания.
Контракты: [CoinGecko](https://docs.coingecko.com/v3.0.1/reference/simple-price),
[ExchangeRate-API](https://www.exchangerate-api.com/docs/standard-requests).

## Пользователи и операции

```text
register --username alice --password 1234
login --username alice --password 1234
show-portfolio
buy --currency BTC --amount 0.05
sell --currency BTC --amount 0.01
show-portfolio --base USD
show-portfolio --base EUR
get-rate --from USD --to BTC
```

Имена уникальны и не могут быть пустыми. Пароль содержит минимум четыре
символа; сохраняется SHA-256 от пароля и индивидуальной случайной соли.
Для имени с пробелами используйте кавычки: `--username "Ann Smith"`.
Открытые пароли не записываются в базу или логи.

После регистрации портфель пуст. Согласно пошаговой логике разделов 2.2
и 3.5 задания, `buy` увеличивает остаток выбранной валюты, а `sell` уменьшает
его. Сумма задаётся в единицах валюты, например `0.05 BTC`. Выводимая стоимость
и выручка в USD являются оценкой; отдельное списание или зачисление USD
не выполняется. Кошелёк автоматически создаётся при первой покупке.

`buy`, `sell` и `show-portfolio` требуют входа. Другой пользователь получает
собственный портфель. Балансы сохраняются между запусками; после перезапуска
нужно войти снова. Поддерживаются USD, EUR, GBP, RUB, BTC, ETH, SOL.
Коды задаются в верхнем регистре, суммы должны быть положительными конечными
числами. Баланс не может стать отрицательным.

Примеры ошибок, после которых сеанс продолжается:

```text
buy --currency BTC --amount -1
sell --currency BTC --amount 100
get-rate --from ABC --to USD
login --username alice --password wrong
```

Интерфейс поясняет неверные аргументы, неизвестную валюту, недостаток средств,
неверный пароль, отсутствие сессии и проблемы сети.

## Кэш, история и данные

В рабочем каталоге используются:

- `data/users.json` — пользователи, хеши, соли и ISO-даты регистрации;
- `data/portfolios.json` — кошельки по идентификатору пользователя;
- `data/rates.json` — `pairs` с курсом, `updated_at`, источником и `last_refresh`;
- `data/exchange_rates.json` — история с ID `FROM_TO_ISO-UTC`, метаданными запроса.

Пустые JSON-файлы включены в проект. Отсутствующие файлы создаются при первой
записи; повреждённый JSON вызывает понятную ошибку и не перезаписывается.
Запись каждого файла атомарна: временный файл в том же каталоге → `os.replace`.
Чтение, изменение и запись защищены блокировкой одного процесса.

Настройки находятся в `[tool.valutatrade]`. TTL кэша — 300 секунд с момента
получения ответа API. Для каждого курса свежесть проверяется отдельно.
`get-rate`, сделки и оценка портфеля при отсутствии свежей пары пытаются
обновить кэш. При неудаче сообщают об устаревании и предлагают `update-rates`.
Просроченное значение не используется в сделке. `show-rates` читает локальный
снимок без сети и помечает устаревшие строки. Обратные и кросс-курсы
вычисляются через USD. Новая пара заменяет старую только при более свежем
`updated_at`; измерения с одинаковым ID в истории не дублируются.

При запуске установленного пакета вне репозитория действуют те же настройки
по умолчанию. `VALUTATRADE_DATA_DIR` и `VALUTATRADE_LOG_DIR` позволяют выбрать
отдельные каталоги данных и логов. Для одной базы используйте тот же каталог.

## Архитектура и логирование

```text
valutatrade_hub/
├── core/
│   ├── currencies.py        # Currency, FiatCurrency, CryptoCurrency и реестр
│   ├── exceptions.py        # доменные исключения
│   ├── models.py            # User, Wallet, Portfolio
│   ├── usecases.py          # регистрация, сессия и сценарии операций
│   └── utils.py             # проверки, UTC-время, TTL и кросс-курсы
├── infra/
│   ├── settings.py          # Singleton SettingsLoader
│   └── database.py          # Singleton DatabaseManager и атомарный JSON
├── parser_service/
│   ├── config.py           # ключи из env, URL, валюты, таймаут и пути
│   ├── api_clients.py      # BaseApiClient и два клиента
│   ├── updater.py          # объединение источников
│   ├── storage.py          # снимок и история
│   └── scheduler.py        # периодическое обновление
├── cli/interface.py        # аргументы, сообщения, PrettyTable
├── decorators.py           # log_action
└── logging_config.py       # формат и ротация журналов
```

`SettingsLoader.get(key, default)` читает общую конфигурацию, `reload()`
перезагружает её. `DatabaseManager` централизует работу с JSON.
Оба Singleton реализованы через `__new__`, поэтому повторное создание
и импорты используют тот же экземпляр.

`@log_action` на `buy/sell` записывает INFO-события в `logs/actions.log`:
ISO-время UTC, действие, пользователя, валюту, сумму, курс, базу и результат.
При ошибке добавляет тип и текст исключения и пробрасывает его в CLI.
Режим `verbose` добавляет остатки «было → стало».
Parser Service ведёт `logs/parser.log` со статусами источников и записи.
По умолчанию формат JSON, уровень INFO; доступны `log_format = "text"`
и `log_level = "DEBUG"`. Ротация — 1 МиБ, три резервных файла.
Журналы и временные файлы исключены из Git.

## Сборка и установка пакета

```console
uv build
uvx twine check dist/*
uv tool install dist/valutatrade_hub-0.1.0-py3-none-any.whl
project
```

При необходимости добавьте каталог инструментов в PATH:
`uv tool update-shell`, затем перезапустите терминал.

## Демонстрация

[![asciicast](https://asciinema.org/a/ROjDd8uOLq8bJ0Wr.svg)](https://asciinema.org/a/ROjDd8uOLq8bJ0Wr)
