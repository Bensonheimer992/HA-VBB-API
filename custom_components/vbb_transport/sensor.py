"""Sensor entities exposing the next departure per selected line/direction."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import VbbConfigEntry
from .const import (
    CONF_LINES,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import VbbDeparturesCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VbbConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create one sensor per configured (line, direction) at the station."""
    coordinator = entry.runtime_data
    station_id: str = entry.data[CONF_STATION_ID]
    station_name: str = entry.data.get(CONF_STATION_NAME, station_id)
    lines: list[dict[str, str]] = entry.data.get(CONF_LINES) or []

    device_info = DeviceInfo(
        identifiers={(DOMAIN, station_id)},
        name=station_name,
        manufacturer=MANUFACTURER,
        model="VBB station",
        configuration_url=f"https://www.vbb.de/fahrinfo/?stop={station_id}",
    )

    entities = [
        VbbDepartureSensor(
            coordinator=coordinator,
            station_id=station_id,
            station_name=station_name,
            line_name=line["name"],
            direction=line.get("direction", ""),
            product=line.get("product", ""),
            device_info=device_info,
        )
        for line in lines
    ]
    async_add_entities(entities)


class VbbDepartureSensor(CoordinatorEntity[VbbDeparturesCoordinator], SensorEntity):
    """Timestamp sensor showing the next actual (delay-adjusted) departure for one line."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: VbbDeparturesCoordinator,
        station_id: str,
        station_name: str,
        line_name: str,
        direction: str,
        product: str,
        device_info: DeviceInfo,
    ) -> None:
        super().__init__(coordinator)
        self._station_id = station_id
        self._station_name = station_name
        self._line_name = line_name
        self._direction = direction
        self._product = product
        self._attr_device_info = device_info

        slug_dir = _slug(direction) if direction else "any"
        self._attr_unique_id = f"{station_id}_{_slug(line_name)}_{slug_dir}"
        if direction:
            self._attr_name = f"{line_name} → {direction}"
        else:
            self._attr_name = line_name
        self._attr_icon = _icon_for_product(product)

    def _matching_departures(self) -> list[dict[str, Any]]:
        data = self.coordinator.data or []
        matches: list[dict[str, Any]] = []
        for dep in data:
            line = (dep.get("line") or {}).get("name")
            if line != self._line_name:
                continue
            if self._direction and (dep.get("direction") or "") != self._direction:
                continue
            matches.append(dep)
        return matches

    @staticmethod
    def _departure_when(dep: dict[str, Any]) -> datetime | None:
        when = dep.get("when") or dep.get("plannedWhen")
        if not when:
            return None
        parsed = dt_util.parse_datetime(when)
        if parsed is None:
            return None
        return dt_util.as_utc(parsed) if parsed.tzinfo else dt_util.as_utc(
            parsed.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        )

    @property
    def native_value(self) -> datetime | None:
        """Return the next actual departure timestamp (delay-adjusted)."""
        now = dt_util.utcnow()
        for dep in self._matching_departures():
            if dep.get("cancelled"):
                continue
            when = self._departure_when(dep)
            if when is None or when < now:
                continue
            return when
        return None

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        matches = self._matching_departures()
        upcoming = matches[0] if matches else {}
        line = upcoming.get("line") or {}

        next_three: list[dict[str, Any]] = []
        now = dt_util.utcnow()
        for dep in matches:
            when = self._departure_when(dep)
            if when is None or when < now:
                continue
            planned = dep.get("plannedWhen")
            next_three.append(
                {
                    "when": when.isoformat(),
                    "planned": planned,
                    "delay_seconds": dep.get("delay"),
                    "platform": dep.get("platform"),
                    "cancelled": bool(dep.get("cancelled")),
                    "trip_id": dep.get("tripId"),
                }
            )
            if len(next_three) >= 3:
                break

        attrs: dict[str, Any] = {
            "station_id": self._station_id,
            "station_name": self._station_name,
            "line": self._line_name,
            "direction": self._direction or None,
            "product": self._product or line.get("product"),
            "operator": (line.get("operator") or {}).get("name"),
            "next_departures": next_three,
        }
        if upcoming:
            attrs["planned"] = upcoming.get("plannedWhen")
            attrs["delay_seconds"] = upcoming.get("delay")
            attrs["platform"] = upcoming.get("platform")
            attrs["cancelled"] = bool(upcoming.get("cancelled"))
            color = line.get("color") or {}
            if color:
                attrs["color"] = color
        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


_PRODUCT_ICONS = {
    "suburban": "mdi:subway-variant",
    "subway": "mdi:subway",
    "tram": "mdi:tram",
    "bus": "mdi:bus",
    "ferry": "mdi:ferry",
    "express": "mdi:train",
    "regional": "mdi:train",
    "regionalexp": "mdi:train",
}


def _icon_for_product(product: str) -> str:
    return _PRODUCT_ICONS.get(product, "mdi:train-bus")


def _slug(value: str) -> str:
    """Make a stable, filesystem-/entity-id-safe slug from arbitrary text."""
    out = []
    for ch in value.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in " -_/→.":
            out.append("_")
    slug = "".join(out).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug or "x"
