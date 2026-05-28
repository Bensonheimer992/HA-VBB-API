"""Async client for the v6 transport.rest API."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=20)


class TransportRestError(RuntimeError):
    """Raised when an upstream call to transport.rest fails."""


class TransportRestClient:
    """Lightweight async client for transport.rest deployments (e.g. v6.vbb.transport.rest)."""

    def __init__(self, session: aiohttp.ClientSession, base_url: str) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")

    @property
    def base_url(self) -> str:
        return self._base_url

    async def _get(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        url = f"{self._base_url}{path}"
        try:
            async with self._session.get(url, params=params, timeout=DEFAULT_TIMEOUT) as response:
                if response.status >= 400:
                    text = await response.text()
                    raise TransportRestError(
                        f"HTTP {response.status} from {url}: {text[:200]}"
                    )
                return await response.json()
        except aiohttp.ClientError as err:
            raise TransportRestError(f"Network error: {err}") from err
        except TimeoutError as err:
            raise TransportRestError("Timeout talking to transport.rest") from err
        except asyncio.TimeoutError as err:
            raise TransportRestError("Timeout talking to transport.rest") from err

    async def search_locations(self, query: str, results: int = 15) -> list[dict[str, Any]]:
        """Search for stops by name. Returns only entries of type 'stop'."""
        data = await self._get(
            "/locations",
            params={
                "query": query,
                "results": results,
                "stops": "true",
                "addresses": "false",
                "poi": "false",
                "fuzzy": "true",
            },
        )
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict) and item.get("type") == "stop"]

    async def get_departures(
        self,
        stop_id: str,
        duration: int = 60,
        results: int = 40,
    ) -> list[dict[str, Any]]:
        """Fetch upcoming departures for a stop. Returns a flat list of departure dicts."""
        data = await self._get(
            f"/stops/{stop_id}/departures",
            params={"duration": duration, "results": results},
        )
        if isinstance(data, dict) and isinstance(data.get("departures"), list):
            return data["departures"]
        if isinstance(data, list):
            return data
        return []
