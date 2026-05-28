"""Smoke test against the live v6.vbb.transport.rest endpoint."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components"))

from vbb_transport.api import TransportRestClient  # noqa: E402
from vbb_transport.config_flow import _extract_lines  # noqa: E402


async def main() -> int:
    async with aiohttp.ClientSession() as session:
        client = TransportRestClient(session, "https://v6.vbb.transport.rest")

        stops = await client.search_locations("Alexanderplatz", results=5)
        assert stops, "expected at least one stop result"
        print(f"Found {len(stops)} stops; first = {stops[0]['name']} ({stops[0]['id']})")

        stop_id = stops[0]["id"]
        departures = await client.get_departures(stop_id, duration=60, results=20)
        print(f"Got {len(departures)} departures")
        if not departures:
            print("No live departures right now — skipping line extraction check.")
            return 0

        sample = departures[0]
        assert "when" in sample, "departure missing 'when' field"
        assert "line" in sample, "departure missing 'line' field"
        print(
            f"Sample: line={sample['line'].get('name')} "
            f"direction={sample.get('direction')!r} "
            f"when={sample.get('when')} "
            f"delay={sample.get('delay')}s"
        )

        lines = _extract_lines(departures)
        print(f"Unique (line, direction) tuples extracted: {len(lines)}")
        for ln in lines[:5]:
            print(f"  - {ln['product']:>10} {ln['name']:<6} -> {ln['direction']}")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
