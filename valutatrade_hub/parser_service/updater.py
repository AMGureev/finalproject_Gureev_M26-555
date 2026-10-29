"""Координация источников с сохранением частично успешного обновления."""

import logging

from valutatrade_hub.core.exceptions import ApiRequestError
from valutatrade_hub.core.utils import iso_now
from valutatrade_hub.parser_service.api_clients import (
    CoinGeckoClient,
    ExchangeRateApiClient,
)
from valutatrade_hub.parser_service.storage import RatesStorage


class RatesUpdater:
    """Обновить все доступные источники, не теряя данные при сбое одного."""

    def __init__(self, clients=None, storage=None):
        self.clients = (
            [CoinGeckoClient(), ExchangeRateApiClient()] if clients is None else clients
        )
        self.storage = storage or RatesStorage()
        self.logger = logging.getLogger("valutatrade.parser")

    def run_update(self, source=None):
        """Вернуть число обновлённых пар, время и список ошибок источников."""
        if source not in (None, "coingecko", "exchangerate"):
            raise ValueError("Источник должен быть coingecko или exchangerate")
        pairs = {}
        errors = []
        self.logger.info("Starting rates update")
        for client in self.clients:
            if source is not None and client.source_key != source:
                continue
            self.logger.info("Fetching from %s", client.source)
            try:
                rates = client.fetch_rates()
                fetched_at = iso_now()
                for pair, rate in rates.items():
                    pairs[pair] = {
                        "rate": rate,
                        "updated_at": fetched_at,
                        "source": client.source,
                        "meta": client.metadata.get(pair, {}),
                    }
                self.logger.info("%s: OK (%d rates)", client.source, len(rates))
            except ApiRequestError as error:
                errors.append(str(error))
                self.logger.error("%s", error)
        if not pairs:
            self.logger.error("No rates updated")
            raise ApiRequestError("; ".join(errors) or "Источники не вернули курсы")
        refreshed_at = iso_now()
        self.storage.save(pairs, refreshed_at)
        self.logger.info("Writing %d rates; update completed", len(pairs))
        return {"count": len(pairs), "last_refresh": refreshed_at, "errors": errors}
