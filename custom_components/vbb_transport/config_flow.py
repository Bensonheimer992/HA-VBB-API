"""Config flow for the VBB Transport integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TransportRestClient, TransportRestError
from .const import (
    CONF_BASE_URL,
    CONF_DURATION,
    CONF_LINES,
    CONF_QUERY,
    CONF_SCAN_INTERVAL,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DEFAULT_BASE_URL,
    DEFAULT_DURATION_MINUTES,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_LINE_KEY_SEP = "||"

# Escalating probe windows used when scanning a freshly picked station for
# lines. Most stations resolve on the first window; the wider fallbacks let
# infrequent stations (last bus already gone, weekend nights) still expose
# their lines without forcing the user to retry during operating hours.
# Each entry is (duration_minutes, max_results).
_LINE_PROBE_WINDOWS: tuple[tuple[int, int], ...] = (
    (120, 80),
    (360, 120),
    (1440, 200),
    (2880, 200),
)


def _line_key(name: str, direction: str) -> str:
    return f"{name}{_LINE_KEY_SEP}{direction}"


def _parse_line_key(key: str) -> tuple[str, str]:
    name, _, direction = key.partition(_LINE_KEY_SEP)
    return name, direction


class VbbConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the multi-step setup for a VBB station + lines."""

    VERSION = 1

    def __init__(self) -> None:
        self._base_url: str = DEFAULT_BASE_URL
        self._query: str = ""
        self._search_results: list[dict[str, Any]] = []
        self._station: dict[str, Any] | None = None
        self._available_lines: list[dict[str, str]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: search for a station by name (and optionally override the API URL)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            query = (user_input.get(CONF_QUERY) or "").strip()
            base_url = (user_input.get(CONF_BASE_URL) or DEFAULT_BASE_URL).strip()
            self._base_url = base_url or DEFAULT_BASE_URL
            self._query = query

            if not query:
                errors["base"] = "empty_query"
            else:
                client = TransportRestClient(async_get_clientsession(self.hass), self._base_url)
                try:
                    stops = await client.search_locations(query, results=15)
                except TransportRestError as err:
                    _LOGGER.warning("transport.rest location search failed: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    if not stops:
                        errors["base"] = "no_stops_found"
                    else:
                        self._search_results = stops
                        return await self.async_step_station()

        schema = vol.Schema(
            {
                vol.Required(CONF_QUERY, default=self._query): str,
                vol.Optional(CONF_BASE_URL, default=self._base_url): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_station(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: select a station from the search results."""
        errors: dict[str, str] = {}

        if user_input is not None:
            station_id = user_input[CONF_STATION_ID]
            station = next(
                (stop for stop in self._search_results if stop.get("id") == station_id),
                None,
            )
            if station is None:
                errors["base"] = "station_not_found"
            else:
                await self.async_set_unique_id(f"{self._base_url}|{station_id}")
                self._abort_if_unique_id_configured()
                self._station = station
                client = TransportRestClient(
                    async_get_clientsession(self.hass), self._base_url
                )
                try:
                    self._available_lines = await _probe_lines(client, station_id)
                except TransportRestError as err:
                    _LOGGER.warning("transport.rest departures probe failed: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    if not self._available_lines:
                        errors["base"] = "no_lines_found"
                    else:
                        return await self.async_step_lines()

        options = [
            selector.SelectOptionDict(
                value=stop["id"],
                label=_format_station_label(stop),
            )
            for stop in self._search_results
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_STATION_ID): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(step_id="station", data_schema=schema, errors=errors)

    async def async_step_lines(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 3: multi-select the lines/directions to create entities for."""
        assert self._station is not None

        if user_input is not None:
            selected_keys: list[str] = user_input.get(CONF_LINES) or []
            lines: list[dict[str, str]] = []
            for key in selected_keys:
                name, direction = _parse_line_key(key)
                match = next(
                    (
                        ln
                        for ln in self._available_lines
                        if ln["name"] == name and ln["direction"] == direction
                    ),
                    None,
                )
                if match is not None:
                    lines.append(match)

            return self.async_create_entry(
                title=self._station["name"],
                data={
                    CONF_BASE_URL: self._base_url,
                    CONF_STATION_ID: self._station["id"],
                    CONF_STATION_NAME: self._station["name"],
                    CONF_LINES: lines,
                },
            )

        options = [
            selector.SelectOptionDict(
                value=_line_key(ln["name"], ln["direction"]),
                label=_format_line_label(ln),
            )
            for ln in self._available_lines
        ]
        schema = vol.Schema(
            {
                vol.Required(CONF_LINES, default=[]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="lines",
            data_schema=schema,
            description_placeholders={"station": self._station["name"]},
        )

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return VbbOptionsFlow()


class VbbOptionsFlow(OptionsFlow):
    """Tune scan interval and how far ahead to look for departures."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS),
                ): vol.All(vol.Coerce(int), vol.Range(min=30, max=900)),
                vol.Optional(
                    CONF_DURATION,
                    default=options.get(CONF_DURATION, DEFAULT_DURATION_MINUTES),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=240)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


def _format_station_label(stop: dict[str, Any]) -> str:
    name = stop.get("name") or stop.get("id") or "Unknown"
    products = stop.get("products") or {}
    modes = [mode for mode, enabled in products.items() if enabled]
    if modes:
        return f"{name}  ·  {', '.join(modes)}"
    return name


def _format_line_label(line: dict[str, str]) -> str:
    name = line["name"]
    direction = line.get("direction") or ""
    product = line.get("product") or ""
    base = f"{name} → {direction}" if direction else name
    if product:
        return f"{base}  ·  {product}"
    return base


async def _probe_lines(
    client: TransportRestClient, stop_id: str
) -> list[dict[str, str]]:
    """Probe departures in escalating windows up to 48h.

    Each window is queried only if the previous returned no usable lines, so
    busy stations still respond instantly while quiet ones still surface
    something to pick from.
    """
    for duration, results in _LINE_PROBE_WINDOWS:
        departures = await client.get_departures(
            stop_id, duration=duration, results=results
        )
        lines = _extract_lines(departures)
        if lines:
            _LOGGER.debug(
                "VBB line probe: %s lines found within %s min for stop %s",
                len(lines),
                duration,
                stop_id,
            )
            return lines
    return []


def _extract_lines(departures: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Build a sorted, deduplicated list of (line, direction, product) tuples."""
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for dep in departures:
        line = dep.get("line") or {}
        name = line.get("name")
        direction = dep.get("direction") or ""
        if not name:
            continue
        key = (name, direction)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "name": name,
                "direction": direction,
                "product": line.get("product") or "",
            }
        )
    result.sort(key=lambda ln: (ln["product"], ln["name"], ln["direction"]))
    return result
