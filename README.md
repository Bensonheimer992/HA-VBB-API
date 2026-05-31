<p align="center">
  <img src="https://raw.githubusercontent.com/Bensonheimer992/HA-VBB-API/refs/heads/main/assets/vbb-logo.svg" alt="VBB logo" width="220">
</p>

# VBB Transport — Home Assistant integration

A HACS-compatible custom integration that turns a [`transport.rest`](https://transport.rest/) v6 endpoint (default: `https://v6.vbb.transport.rest`) into Home Assistant sensors showing the **next actual departure time** (delay included) for every line you care about, at every station you care about.

> The VBB logo is a trademark of Verkehrsverbund Berlin-Brandenburg GmbH. Source: [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:VBB-Logo.svg). It is included here for identification purposes only — this project is not affiliated with VBB.

## What you get

For each station you configure, you pick which lines + directions interest you. Each selection becomes one timestamp sensor:

- **State:** the next non-cancelled departure as a UTC timestamp (delay-adjusted — i.e. the API's `when` field, not `plannedWhen`).
- **Device class:** `timestamp`, so Lovelace renders it as a relative time ("in 4 min").
- **Attributes:** `planned`, `delay_seconds`, `platform`, `cancelled`, `operator`, `color`, plus a `next_departures` list of the next 3 trips.

All entities for one station are grouped under one Home Assistant device.

## Setup with UV (for development)

```powershell
uv venv --python 3.13
uv sync
.venv\Scripts\python.exe tests\test_api_live.py     # smoke-test the live API
.venv\Scripts\python.exe tests\test_sensor_logic.py # unit-test sensor logic
```

## Installation

### Via HACS (custom repository)

1. HACS → Integrations → ⋮ → *Custom repositories*
2. Add `https://github.com/Bensonheimer992/HA-VBB-API` as type *Integration*.
3. Install **VBB Transport (Berlin/Brandenburg)**, then restart Home Assistant.

### Manual

Copy `custom_components/vbb_transport/` into your Home Assistant `config/custom_components/` directory and restart.

## Configuration

1. *Settings → Devices & Services → Add Integration → "VBB Transport"*.
2. **Step 1** — Type (part of) a station name (e.g. *Alexanderplatz*). Leave the API base URL at the default unless you want a different `transport.rest` instance (e.g. BVG, DB, ÖBB).
3. **Step 2** — Pick one of the matched stations.
4. **Step 3** — Pick one or more `Line → Direction` combinations from the lines currently serving that station.
5. Each selected line gets its own sensor under one device named after the station.

Repeat the flow for additional stations.

## Options

After setup, *Configure* on the integration entry lets you tune:

- **Polling interval** (seconds, default 60 — be polite, the API has a 100 req/min limit)
- **Departure look-ahead** (minutes, default 60)

## Brand icon — Home Assistant vs. the HACS store

A logo shows up in **two** different places, and they don't share a source:

**1. Home Assistant's own *Devices & Services* page — works out of the box.**
The integration ships its brand assets in `custom_components/vbb_transport/brand/`, served by HA's [Brand Proxy API](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/) (HA 2026.3+) at `/api/brands/integration/vbb_transport/icon.png`, with stale-while-revalidate caching so the logo survives internet outages.

```
custom_components/vbb_transport/brand/
├── icon.png       256x256   (slight padding, tuned for HA's UI)
├── icon@2x.png    512x512
├── logo.png       238x256
└── logo@2x.png    477x512
```

**2. The HACS store / downloads panel — needs a one-time `home-assistant/brands` PR.**
HACS does **not** read the local Brand Proxy yet (see hacs/integration [#5171](https://github.com/hacs/integration/issues/5171) and [#5223](https://github.com/hacs/integration/issues/5223)); its frontend still loads icons from `brands.home-assistant.io`. Until that ships, the HACS card shows an *"icon not available"* placeholder unless the brand is registered in that repo.

To register it, submit the staged set in `assets/brands/custom_integrations/vbb_transport/` (icons trimmed edge-to-edge, as brands requires) to [home-assistant/brands](https://github.com/home-assistant/brands):

1. Fork `home-assistant/brands`.
2. Copy `assets/brands/custom_integrations/vbb_transport/` into the fork at the **same path**.
3. Open a PR. Once merged, `brands.home-assistant.io/_/vbb_transport/icon.png` serves the real logo and the HACS card picks it up.

To re-render both sets from `assets/vbb-logo.svg` after editing the source SVG:

```powershell
uv sync --group brand-tools
.venv\Scripts\python.exe scripts\render_brand_pngs.py
```

## Notes & limitations

- The integration uses the public `transport.rest` v6 API. It works for any v6 instance that returns the same shape — BVG (`v6.bvg.transport.rest`), DB (`v6.db.transport.rest`), etc. Pop the URL into the first config step.
- Lines are detected by *probing the live departure board* during setup. A line that doesn't run at the moment you configure the station won't be offered — re-run *Add Integration* during operating hours to add it later.
- "Direction" is taken from `departure.direction` — the actual destination text from the operator, so values like `S Hackescher Markt` or `Mitte, Memhardstr.` are used verbatim.

## License

MIT.
