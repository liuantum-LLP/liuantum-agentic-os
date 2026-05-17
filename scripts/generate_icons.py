#!/usr/bin/env python3
from __future__ import annotations

import binascii
import math
import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "apps" / "desktop" / "src-tauri" / "icons"

# Premium abstract AI agentic OS icon — neural orbit mark.
# Design: luminous core, orbiting agent nodes, radial data rings.
# Generated offline. No external dependencies.

PNG_SIZES = {
    "32x32.png": 32,
    "128x128.png": 128,
    "128x128@2x.png": 256,
    "Square30x30Logo.png": 30,
    "Square44x44Logo.png": 44,
    "Square71x71Logo.png": 71,
    "Square89x89Logo.png": 89,
    "Square107x107Logo.png": 107,
    "Square142x142Logo.png": 142,
    "Square150x150Logo.png": 150,
    "Square284x284Logo.png": 284,
    "Square310x310Logo.png": 310,
    "StoreLogo.png": 50,
}


def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    body = chunk_type + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", binascii.crc32(body) & 0xFFFFFFFF)


def make_png(size: int) -> bytes:
    cx = size * 0.5
    cy = size * 0.5
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            nx = (x / max(size - 1, 1)) * 2.0 - 1.0
            ny = (y / max(size - 1, 1)) * 2.0 - 1.0
            r, g, b, a = _agent_orbit_pixel(x, y, nx, ny, cx, cy, size)
            row.extend((r, g, b, a))
        rows.append(bytes(row))
    raw = b"".join(rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(raw, 9))
        + png_chunk(b"IEND", b"")
    )


def _agent_orbit_pixel(
    x: int, y: int, nx: float, ny: float, cx: float, cy: float, size: int
) -> tuple[int, int, int, int]:
    s = max(size, 1)
    dist = math.sqrt(nx * nx + ny * ny)

    # Background: deep space gradient
    bg_r = int(8 + 6 * (ny * 0.5 + 0.5))
    bg_g = int(12 + 10 * (nx * 0.3 + 0.5))
    bg_b = int(22 + 14 * (ny * 0.4 + 0.5))

    er = 0
    eg = 0
    eb = 0

    # Outer glow ring
    ring_rad = 0.52
    ring_width = 0.04
    ring_dist = abs(dist - ring_rad)
    if ring_dist < ring_width:
        t = ring_dist / ring_width
        intensity = math.cos(t * math.pi * 0.5)
        er += int(40 * intensity)
        eg += int(90 * intensity)
        eb += int(180 * intensity)

    # Inner orbit ring
    inner_ring = 0.32
    inner_width = 0.025
    inner_dist = abs(dist - inner_ring)
    if inner_dist < inner_width:
        t = inner_dist / inner_width
        intensity = math.cos(t * math.pi * 0.5) * 0.6
        er += int(30 * intensity)
        eg += int(70 * intensity)
        eb += int(150 * intensity)

    # Agent nodes on outer ring (3 nodes)
    angles = [0.0, 2.094, 4.189]
    node_radius = 0.055
    for idx, angle in enumerate(angles):
        npx = cx + size * ring_rad * math.cos(angle)
        npy = cy + size * ring_rad * math.sin(angle)
        nd = math.sqrt((x - npx) ** 2 + (y - npy) ** 2)
        if nd < size * node_radius:
            t = nd / (size * node_radius)
            glow = 1.0 - t * t
            er += int(180 * glow)
            eg += int(220 * glow)
            eb += int(255 * glow)
        # Connection arcs between nodes
        next_angle = angles[(idx + 1) % len(angles)]
        arc_steps = 24
        for seg in range(arc_steps + 1):
            frac = seg / arc_steps
            ax = cx + size * ring_rad * math.cos(angle + frac * (next_angle - angle))
            ay = cy + size * ring_rad * math.sin(angle + frac * (next_angle - angle))
            ad = math.sqrt((x - ax) ** 2 + (y - ay) ** 2)
            if ad < max(1.2, size * 0.01):
                er += int(80)
                eg += int(160)
                eb += int(240)

    # Small data-flow dots on inner ring
    for dot_idx in range(8):
        da = dot_idx * 0.785
        dpx = cx + size * inner_ring * math.cos(da)
        dpy = cy + size * inner_ring * math.sin(da)
        dd = math.sqrt((x - dpx) ** 2 + (y - dpy) ** 2)
        if dd < max(1.0, size * 0.012):
            eg += 150
            eb += 220

    # Central core — bright luminous orchestrator
    cd = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    if cd < size * 0.07:
        t = cd / (size * 0.07)
        glow = 1.0 - t * t * t
        er = min(255, er + int(255 * glow))
        eg = min(255, eg + int(255 * glow))
        eb = min(255, eb + int(255 * glow))
    elif cd < size * 0.12:
        t = (cd - size * 0.07) / (size * 0.05)
        glow = 1.0 - t
        er = min(255, er + int(120 * glow))
        eg = min(255, eg + int(180 * glow))
        eb = min(255, eb + int(255 * glow))

    # Subtle glow haze near center
    if dist < 0.25:
        t = dist / 0.25
        haze = (1.0 - t) * 0.15
        er = min(255, er + int(15 * haze))
        eg = min(255, eg + int(40 * haze))
        eb = min(255, eb + int(80 * haze))

    r = min(255, bg_r + er)
    g = min(255, bg_g + eg)
    b = min(255, bg_b + eb)
    a = 255

    # Rounded-square mask for very small icons
    edge = max(abs(nx), abs(ny))
    if size < 64 and edge > 0.78:
        fade = (edge - 0.78) / 0.22
        a = max(0, int(255 * (1.0 - fade * fade * fade)))

    return (r, g, b, a)


def write_svg() -> None:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512" role="img" aria-label="Liuant Agentic OS icon">
  <defs>
    <radialGradient id="bg" cx="50%" cy="50%" r="55%">
      <stop offset="0%" stop-color="#121a33"/>
      <stop offset="100%" stop-color="#080c18"/>
    </radialGradient>
    <linearGradient id="ring" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#4f8cf7"/>
      <stop offset="50%" stop-color="#9b6ff6"/>
      <stop offset="100%" stop-color="#2dd4e8"/>
    </linearGradient>
    <radialGradient id="core" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="1"/>
      <stop offset="40%" stop-color="#b8cfff" stop-opacity="0.8"/>
      <stop offset="100%" stop-color="#4f8cf7" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="conn" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#4f8cf7" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="#9b6ff6" stop-opacity="0.3"/>
    </linearGradient>
  </defs>
  <rect width="512" height="512" rx="112" fill="url(#bg)"/>
  <circle cx="256" cy="256" r="130" fill="none" stroke="url(#ring)" stroke-width="2.5" opacity="0.5"/>
  <circle cx="256" cy="256" r="82" fill="none" stroke="url(#ring)" stroke-width="1.5" opacity="0.3"/>
  <circle cx="256" cy="126" r="16" fill="#4f8cf7" opacity="0.95">
    <animate attributeName="opacity" values="0.95;0.6;0.95" dur="3s" repeatCount="indefinite"/>
  </circle>
  <circle cx="369" cy="348" r="16" fill="#9b6ff6" opacity="0.95">
    <animate attributeName="opacity" values="0.6;0.95;0.6" dur="3s" repeatCount="indefinite"/>
  </circle>
  <circle cx="143" cy="348" r="16" fill="#2dd4e8" opacity="0.95">
    <animate attributeName="opacity" values="0.8;0.5;0.8" dur="3s" repeatCount="indefinite"/>
  </circle>
  <line x1="256" y1="126" x2="369" y2="348" stroke="url(#conn)" stroke-width="2"/>
  <line x1="369" y1="348" x2="143" y2="348" stroke="url(#conn)" stroke-width="2"/>
  <line x1="143" y1="348" x2="256" y2="126" stroke="url(#conn)" stroke-width="2"/>
  <circle cx="256" cy="256" r="28" fill="url(#core)" opacity="0.9"/>
  <circle cx="256" cy="256" r="10" fill="#ffffff" opacity="0.95"/>
  <circle cx="213" cy="224" r="3.5" fill="#4f8cf7" opacity="0.6"/>
  <circle cx="299" cy="224" r="3.5" fill="#9b6ff6" opacity="0.6"/>
  <circle cx="256" cy="316" r="3.5" fill="#2dd4e8" opacity="0.6"/>
  <circle cx="274" cy="248" r="2.5" fill="#e0eaff" opacity="0.4"/>
  <circle cx="238" cy="264" r="2.5" fill="#e0eaff" opacity="0.4"/>
  <circle cx="272" cy="280" r="2" fill="#e0eaff" opacity="0.3"/>
</svg>
"""
    (ICON_DIR / "icon.svg").write_text(svg, encoding="utf-8")


def write_ico(pngs: list[tuple[int, bytes]]) -> None:
    entries = []
    images = []
    offset = 6 + 16 * len(pngs)
    for size, data in pngs:
        size_byte = 0 if size >= 256 else size
        entries.append(struct.pack("<BBBBHHII", size_byte, size_byte, 0, 0, 1, 32, len(data), offset))
        images.append(data)
        offset += len(data)
    (ICON_DIR / "icon.ico").write_bytes(struct.pack("<HHH", 0, 1, len(pngs)) + b"".join(entries) + b"".join(images))


def write_icns(png_512: bytes) -> None:
    element = b"ic10" + struct.pack(">I", len(png_512) + 8) + png_512
    (ICON_DIR / "icon.icns").write_bytes(b"icns" + struct.pack(">I", len(element) + 8) + element)


def main() -> None:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    write_svg()
    generated: dict[int, bytes] = {}
    for name, size in PNG_SIZES.items():
        data = generated.setdefault(size, make_png(size))
        (ICON_DIR / name).write_bytes(data)
    write_ico([(32, generated[32]), (128, generated[128]), (256, generated[256])])
    write_icns(make_png(512))
    print(f"Generated brand icons in {ICON_DIR}")


if __name__ == "__main__":
    main()
