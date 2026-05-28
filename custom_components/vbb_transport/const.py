"""Constants for the VBB Transport integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "vbb_transport"

DEFAULT_BASE_URL: Final = "https://v6.vbb.transport.rest"
DEFAULT_SCAN_INTERVAL_SECONDS: Final = 60
DEFAULT_DURATION_MINUTES: Final = 60
DEFAULT_RESULTS: Final = 40

CONF_BASE_URL: Final = "base_url"
CONF_STATION_ID: Final = "station_id"
CONF_STATION_NAME: Final = "station_name"
CONF_LINES: Final = "lines"
CONF_QUERY: Final = "query"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_DURATION: Final = "duration"

MANUFACTURER: Final = "transport.rest"
