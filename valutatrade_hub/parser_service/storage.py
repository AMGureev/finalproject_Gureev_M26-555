"""Последний снимок курсов и история уникальных измерений."""

from valutatrade_hub.core.currencies import validate_code
from valutatrade_hub.core.utils import parse_timestamp, validate_number
from valutatrade_hub.infra.database import DatabaseManager
from valutatrade_hub.parser_service.config import ParserConfig


class RatesStorage:
    """Записывать проверенные измерения и снимок атомарно для каждого файла."""

    def __init__(self, config=None, database=None):
        self.config = config or ParserConfig()
        self.database = database or DatabaseManager()

    def save(self, pairs, last_refresh):
        """Добавить уникальные замеры, заменив в кэше только более старые пары."""
        parse_timestamp(last_refresh)
        records = []
        for pair, value in pairs.items():
            from_code, to_code = pair.split("_")
            validate_code(from_code)
            validate_code(to_code)
            rate = validate_number(value["rate"])
            parse_timestamp(value["updated_at"])
            records.append(
                {
                    "id": f"{pair}_{value['updated_at']}",
                    "from_currency": from_code,
                    "to_currency": to_code,
                    "rate": rate,
                    "timestamp": value["updated_at"],
                    "source": value["source"],
                    "meta": value.get("meta", {}),
                }
            )

        def append_history(history):
            """Не дублировать измерения с одной парой и временем."""
            known = {record["id"] for record in history}
            history.extend(record for record in records if record["id"] not in known)

        def update_snapshot(snapshot):
            """Сохранить прежние пары при частичном обновлении источников."""
            current = snapshot.setdefault("pairs", {})
            for pair, value in pairs.items():
                old = current.get(pair)
                if old is None or parse_timestamp(
                    value["updated_at"]
                ) > parse_timestamp(old["updated_at"]):
                    current[pair] = {
                        key: value[key] for key in ("rate", "updated_at", "source")
                    }
            previous = snapshot.get("last_refresh")
            if previous is None or parse_timestamp(last_refresh) > parse_timestamp(
                previous
            ):
                snapshot["last_refresh"] = last_refresh

        self.database.update(self.config.HISTORY_FILE_PATH, append_history, [])
        self.database.update(
            self.config.RATES_FILE_PATH, update_snapshot, {"pairs": {}}
        )
