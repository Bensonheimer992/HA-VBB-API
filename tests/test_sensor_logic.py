"""Unit-test the departure-picking logic of VbbDepartureSensor without a HA runtime."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components"))

from homeassistant.helpers.device_registry import DeviceInfo  # noqa: E402

from vbb_transport.sensor import VbbDepartureSensor  # noqa: E402


def _dep(line_name: str, direction: str, when_iso: str, delay: int | None = 0, cancelled: bool = False) -> dict:
    return {
        "line": {"name": line_name, "product": "tram", "operator": {"name": "BVG"}},
        "direction": direction,
        "when": when_iso,
        "plannedWhen": when_iso,
        "delay": delay,
        "platform": "Pos. 15",
        "cancelled": cancelled,
        "tripId": f"trip-{line_name}-{when_iso}",
    }


def _now_iso(offset_minutes: int) -> str:
    return (
        datetime.now(timezone.utc).replace(microsecond=0)
        + timedelta(minutes=offset_minutes)
    ).isoformat()


def _make_sensor(data: list[dict]) -> VbbDepartureSensor:
    coordinator = SimpleNamespace(
        data=data,
        last_update_success=True,
        async_add_listener=lambda *_args, **_kwargs: (lambda: None),
    )
    return VbbDepartureSensor(
        coordinator=coordinator,  # type: ignore[arg-type]
        station_id="900100003",
        station_name="S+U Alexanderplatz",
        line_name="M6",
        direction="S Hackescher Markt",
        product="tram",
        device_info=DeviceInfo(identifiers={("vbb_transport", "900100003")}),
    )


def test_returns_next_future_departure_for_matching_line() -> None:
    data = [
        _dep("M6", "S Hackescher Markt", _now_iso(-2)),   # past — skip
        _dep("M6", "Riese", _now_iso(3)),                  # wrong direction — skip
        _dep("M6", "S Hackescher Markt", _now_iso(5)),     # ← winner
        _dep("M6", "S Hackescher Markt", _now_iso(20)),    # later
    ]
    sensor = _make_sensor(data)
    value = sensor.native_value
    assert value is not None, "expected a timestamp"
    delta_seconds = (value - datetime.now(timezone.utc)).total_seconds()
    assert 240 < delta_seconds < 360, f"expected ~5min out, got {delta_seconds}"


def test_skips_cancelled_departures() -> None:
    data = [
        _dep("M6", "S Hackescher Markt", _now_iso(2), cancelled=True),
        _dep("M6", "S Hackescher Markt", _now_iso(10)),
    ]
    sensor = _make_sensor(data)
    value = sensor.native_value
    assert value is not None
    delta_seconds = (value - datetime.now(timezone.utc)).total_seconds()
    assert 540 < delta_seconds < 660


def test_returns_none_when_no_match() -> None:
    data = [
        _dep("M5", "S Hackescher Markt", _now_iso(3)),
        _dep("M6", "Wrong direction", _now_iso(3)),
    ]
    sensor = _make_sensor(data)
    assert sensor.native_value is None


def test_extra_state_attributes_includes_delay_and_next_three() -> None:
    data = [
        _dep("M6", "S Hackescher Markt", _now_iso(3), delay=420),
        _dep("M6", "S Hackescher Markt", _now_iso(13), delay=0),
        _dep("M6", "S Hackescher Markt", _now_iso(23), delay=60),
        _dep("M6", "S Hackescher Markt", _now_iso(33), delay=0),
    ]
    sensor = _make_sensor(data)
    attrs = sensor.extra_state_attributes
    assert attrs["line"] == "M6"
    assert attrs["direction"] == "S Hackescher Markt"
    assert attrs["delay_seconds"] == 420
    assert attrs["operator"] == "BVG"
    assert len(attrs["next_departures"]) == 3
    assert attrs["next_departures"][0]["delay_seconds"] == 420


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"OK: {name}")
    print("All tests passed.")
