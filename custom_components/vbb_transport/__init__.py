"""The VBB Transport (Berlin/Brandenburg) integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TransportRestClient
from .const import CONF_BASE_URL, DEFAULT_BASE_URL, DOMAIN
from .coordinator import VbbDeparturesCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type VbbConfigEntry = ConfigEntry[VbbDeparturesCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: VbbConfigEntry) -> bool:
    """Set up a configured VBB station."""
    base_url = entry.data.get(CONF_BASE_URL) or DEFAULT_BASE_URL
    client = TransportRestClient(async_get_clientsession(hass), base_url)
    coordinator = VbbDeparturesCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VbbConfigEntry) -> bool:
    """Unload a configured VBB station."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: VbbConfigEntry) -> None:
    """Reload the entry when options change (scan interval, duration)."""
    await hass.config_entries.async_reload(entry.entry_id)
