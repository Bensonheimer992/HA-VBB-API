"""DataUpdateCoordinator polling departures for one configured station."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TransportRestClient, TransportRestError
from .const import (
    CONF_DURATION,
    CONF_SCAN_INTERVAL,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DEFAULT_DURATION_MINUTES,
    DEFAULT_RESULTS,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class VbbDeparturesCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Poll one stop's departure board and expose the raw list to platforms."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: TransportRestClient,
    ) -> None:
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL) or DEFAULT_SCAN_INTERVAL_SECONDS
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {entry.data.get(CONF_STATION_NAME, entry.data[CONF_STATION_ID])}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self._client = client
        self._station_id: str = entry.data[CONF_STATION_ID]
        self._duration: int = entry.options.get(CONF_DURATION) or DEFAULT_DURATION_MINUTES

    async def _async_update_data(self) -> list[dict[str, Any]]:
        try:
            return await self._client.get_departures(
                self._station_id,
                duration=self._duration,
                results=DEFAULT_RESULTS,
            )
        except TransportRestError as err:
            raise UpdateFailed(str(err)) from err
