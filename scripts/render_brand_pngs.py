"""Render assets/vbb-logo.svg to the PNG variants the HA Brand Proxy API serves.

Since Home Assistant 2026.3 (https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/),
custom integrations can ship their own brand assets in custom_components/<domain>/brand/.
HA serves them via /api/brands/integration/<domain>/<image>, and HACS shows them on the
integration card — no PR to home-assistant/brands required.

Supported filenames:
- icon.png         square icon, transparent
- icon@2x.png      square icon @2x, transparent
- logo.png         full logo (any aspect), transparent
- logo@2x.png      full logo @2x, transparent
(`dark_*` variants are also supported but skipped here — our SVG is one-colour.)

Uses resvg-py (pure-Rust SVG renderer, no native Cairo dependency).
"""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

from PIL import Image
from resvg_py import svg_to_bytes

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets" / "vbb-logo.svg"
OUT = ROOT / "custom_components" / "vbb_transport" / "brand"

# Pad inside the square icon so the logo doesn't touch the edge.
ICON_PADDING_RATIO = 0.08


def _render_master() -> Image.Image:
    """Render the SVG at high resolution once; we resample for each output size."""
    png_bytes = svg_to_bytes(svg_path=str(SRC), width=2048)
    return Image.open(BytesIO(bytes(png_bytes))).convert("RGBA")


def _square_icon(master: Image.Image, size: int) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    inner = int(size * (1 - 2 * ICON_PADDING_RATIO))
    scale = min(inner / master.width, inner / master.height)
    new_w = max(1, int(master.width * scale))
    new_h = max(1, int(master.height * scale))
    resized = master.resize((new_w, new_h), Image.LANCZOS)
    pos = ((size - new_w) // 2, (size - new_h) // 2)
    canvas.paste(resized, pos, resized)
    return canvas


def _logo_at_height(master: Image.Image, target_h: int) -> Image.Image:
    scale = target_h / master.height
    new_w = max(1, int(master.width * scale))
    return master.resize((new_w, target_h), Image.LANCZOS)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    master = _render_master()
    print(f"Master rendered at {master.width}x{master.height}")

    outputs = {
        "icon.png": _square_icon(master, 256),
        "icon@2x.png": _square_icon(master, 512),
        "logo.png": _logo_at_height(master, 256),
        "logo@2x.png": _logo_at_height(master, 512),
    }
    for name, img in outputs.items():
        path = OUT / name
        img.save(path, "PNG", optimize=True)
        print(f"  {name:14s}  {img.size[0]:>4}x{img.size[1]:<4}  {path.stat().st_size:>6} bytes")

    print(f"\nWritten to {OUT.relative_to(ROOT)} — HA will serve these via /api/brands/integration/vbb_transport/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
