"""Unit-test the config flow helpers (the HA test harness needs `fcntl`, which is Unix-only)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components"))

from vbb_transport.config_flow import (  # noqa: E402
    _LINE_PROBE_DURATION_MINUTES,
    _LINE_PROBE_RESULTS,
    _extract_lines,
    _format_line_label,
    _format_station_label,
    _line_key,
    _parse_line_key,
    _probe_lines,
)


def test_line_key_roundtrip() -> None:
    key = _line_key("M6", "S Hackescher Markt")
    assert _parse_line_key(key) == ("M6", "S Hackescher Markt")


def test_line_key_handles_empty_direction() -> None:
    key = _line_key("S3", "")
    assert _parse_line_key(key) == ("S3", "")


def test_extract_lines_dedupes_and_sorts() -> None:
    departures = [
        {"line": {"name": "M6", "product": "tram"}, "direction": "S Hackescher Markt"},
        {"line": {"name": "M6", "product": "tram"}, "direction": "S Hackescher Markt"},  # dup
        {"line": {"name": "100", "product": "bus"}, "direction": "Mitte"},
        {"line": {"name": "M6", "product": "tram"}, "direction": "Riese"},   # other direction
        {"line": {"name": ""},   "direction": "ignored"},                    # no line name -> skipped
        {"line": None, "direction": "ignored"},                              # null line -> skipped
    ]
    out = _extract_lines(departures)
    keys = [(ln["name"], ln["direction"]) for ln in out]
    assert ("M6", "S Hackescher Markt") in keys
    assert ("M6", "Riese") in keys
    assert ("100", "Mitte") in keys
    assert len(out) == 3  # dedup + skip


def test_extract_lines_handles_missing_direction() -> None:
    departures = [{"line": {"name": "U2", "product": "subway"}}]
    out = _extract_lines(departures)
    assert out == [{"name": "U2", "direction": "", "product": "subway"}]


def test_format_station_label_includes_active_products() -> None:
    stop = {
        "id": "900100003",
        "name": "S+U Alexanderplatz Bhf (Berlin)",
        "products": {"suburban": True, "subway": True, "bus": False},
    }
    label = _format_station_label(stop)
    assert "S+U Alexanderplatz" in label
    assert "suburban" in label
    assert "subway" in label
    assert "bus" not in label


def _dep(line: str, direction: str) -> dict:
    return {"line": {"name": line, "product": "tram"}, "direction": direction}


def test_probe_lines_always_uses_48h_window() -> None:
    client = AsyncMock()
    client.get_departures.return_value = [_dep("M6", "S Hackescher Markt")]

    result = asyncio.run(_probe_lines(client, "900100003"))

    assert client.get_departures.await_count == 1
    args, kwargs = client.get_departures.await_args
    assert kwargs["duration"] == _LINE_PROBE_DURATION_MINUTES == 2880
    assert kwargs["results"] == _LINE_PROBE_RESULTS
    assert result[0]["name"] == "M6"


def test_probe_lines_returns_empty_when_no_departures() -> None:
    client = AsyncMock()
    client.get_departures.return_value = []

    result = asyncio.run(_probe_lines(client, "900100003"))

    assert result == []
    assert client.get_departures.await_count == 1


def test_format_line_label_with_and_without_direction() -> None:
    with_dir = _format_line_label(
        {"name": "M6", "direction": "S Hackescher Markt", "product": "tram"}
    )
    assert "M6" in with_dir and "S Hackescher Markt" in with_dir and "tram" in with_dir

    no_dir = _format_line_label({"name": "S3", "direction": "", "product": "suburban"})
    assert no_dir.startswith("S3")
    assert "suburban" in no_dir


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK: {name}")
    print("All tests passed.")
