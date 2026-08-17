#!/usr/bin/env python3
"""Render every README SVG as deterministic light and dark 2x PNGs."""

from __future__ import annotations

import html
import re
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
IMAGE_DIR = ROOT / "docs" / "img"
CHROMIUM = Path("/opt/pw-browsers/chromium")
SCALE = 2
MINIMUM_WINDOW = 600
VIEWPORT_SLACK = 200
MINIMUM_PNG_BYTES = 10 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
DARK_MEDIA_START = re.compile(
    r"@media\s*\(\s*prefers-color-scheme\s*:\s*dark\s*\)\s*\{"
)


def _view_box(svg_text: str, source: Path) -> tuple[int, int]:
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as error:
        raise RuntimeError(f"{source}: invalid SVG XML: {error}") from error

    raw_view_box = root.get("viewBox")
    if raw_view_box is None:
        raise RuntimeError(f"{source}: SVG has no viewBox")

    try:
        _, _, width, height = (float(part) for part in raw_view_box.split())
    except (TypeError, ValueError) as error:
        raise RuntimeError(f"{source}: invalid viewBox {raw_view_box!r}") from error
    if width <= 0 or height <= 0:
        raise RuntimeError(f"{source}: viewBox dimensions must be positive")
    if not width.is_integer() or not height.is_integer():
        raise RuntimeError(f"{source}: viewBox dimensions must be whole CSS pixels")
    return int(width), int(height)


def _dark_media_bounds(svg_text: str, source: Path) -> tuple[int, int, int]:
    match = DARK_MEDIA_START.search(svg_text)
    if match is None:
        raise RuntimeError(f"{source}: no prefers-color-scheme: dark block")

    opening_brace = match.end() - 1
    depth = 0
    closing_brace = -1
    for index in range(opening_brace, len(svg_text)):
        if svg_text[index] == "{":
            depth += 1
        elif svg_text[index] == "}":
            depth -= 1
            if depth == 0:
                closing_brace = index
                break
    if closing_brace < 0:
        raise RuntimeError(f"{source}: unterminated dark-mode media block")
    if DARK_MEDIA_START.search(svg_text, closing_brace + 1) is not None:
        raise RuntimeError(f"{source}: expected exactly one dark-mode media block")
    return match.start(), opening_brace, closing_brace


def _themed_svg(svg_text: str, source: Path, *, dark: bool) -> str:
    start, opening_brace, closing_brace = _dark_media_bounds(svg_text, source)
    if dark:
        # The dark rules follow the base rules at equal specificity. Removing only
        # the media wrapper promotes those declarations to unconditional overrides.
        replacement = svg_text[opening_brace + 1 : closing_brace]
    else:
        # Removing the media block makes the light rendering independent of the
        # machine or browser's own color-scheme preference.
        replacement = ""
    return svg_text[:start] + replacement + svg_text[closing_brace + 1 :]


def _wrapper(svg: Path, width: int, height: int, *, dark: bool) -> str:
    source = html.escape(svg.resolve().as_uri(), quote=True)
    background = "#0d1117" if dark else "#ffffff"
    # The 2x factor is baked into the CSS size rather than passed as
    # --force-device-scale-factor: under --headless=new that flag scales the
    # content but not the capture viewport, clipping the bottom-right of every
    # image (observed and bisected on this Chromium build).
    scaled_width, scaled_height = width * SCALE, height * SCALE
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    html, body {{
      margin: 0;
      width: {scaled_width}px;
      height: {scaled_height}px;
      overflow: hidden;
      background: {background};
    }}
    img {{ display: block; width: {scaled_width}px; height: {scaled_height}px; }}
  </style>
</head>
<body><img src="{source}" alt=""></body>
</html>
"""


def _render(
    wrapper: Path, output: Path, width: int, height: int, profile_dir: Path
) -> None:
    # --headless=new is required: legacy --headless hangs indefinitely on this
    # Chromium build (observed under both the old and a fresh profile), and
    # /dev/shm in the container is too small for the default shared-memory path.
    command = [
        str(CHROMIUM),
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        f"--user-data-dir={profile_dir}",
        "--hide-scrollbars",
        f"--screenshot={output}",
        # --headless=new reserves an 88px strip of the window for browser UI
        # (measured: every capture's viewport is window-height minus exactly
        # 88px) and also clamps small window heights. Render with generous
        # headroom and crop to the exact size afterwards.
        f"--window-size={width * SCALE},{max(height * SCALE + VIEWPORT_SLACK, MINIMUM_WINDOW)}",
        wrapper.resolve().as_uri(),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    print(f"Chromium {output.name}: exit code {result.returncode}")
    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        raise RuntimeError(
            f"Chromium exited {result.returncode} while rendering {output.name}"
            + (f":\n{details}" if details else "")
        )
    if not output.is_file():
        raise RuntimeError(f"Chromium did not create {output}")
    _crop(output, width * SCALE, height * SCALE)


def _crop(path: Path, width: int, height: int) -> None:
    """Trim the minimum-window padding down to the exact target size."""
    from PIL import Image

    with Image.open(path) as image:
        if image.size == (width, height):
            return
        if image.size[0] < width or image.size[1] < height:
            raise RuntimeError(
                f"{path}: captured {image.size[0]}x{image.size[1]}, "
                f"smaller than the target {width}x{height}"
            )
        image.crop((0, 0, width, height)).save(path)


def _png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as png:
        header = png.read(24)
    if len(header) != 24 or header[:8] != PNG_SIGNATURE:
        raise RuntimeError(f"{path}: not a PNG")
    if struct.unpack(">I", header[8:12])[0] != 13 or header[12:16] != b"IHDR":
        raise RuntimeError(f"{path}: missing canonical IHDR header")
    return struct.unpack(">II", header[16:24])


def _validate_png(path: Path, width: int, height: int) -> None:
    size = path.stat().st_size
    if size <= MINIMUM_PNG_BYTES:
        raise RuntimeError(
            f"{path}: {size} bytes is not greater than {MINIMUM_PNG_BYTES} bytes"
        )

    actual = _png_dimensions(path)
    if actual[0] * height != actual[1] * width:
        raise RuntimeError(
            f"{path}: {actual[0]}x{actual[1]} does not match "
            f"the SVG aspect ratio {width}:{height}"
        )
    expected = width * SCALE, height * SCALE
    if actual != expected:
        raise RuntimeError(
            f"{path}: got {actual[0]}x{actual[1]}, "
            f"expected {expected[0]}x{expected[1]}"
        )


def main() -> int:
    if not CHROMIUM.is_file():
        raise RuntimeError(f"Chromium binary not found at {CHROMIUM}")

    sources = sorted(IMAGE_DIR.glob("*.svg"))
    if not sources:
        raise RuntimeError(f"no SVG files found in {IMAGE_DIR}")

    with tempfile.TemporaryDirectory(
        prefix=".ward-readme-images-", dir=IMAGE_DIR
    ) as temporary:
        temporary_dir = Path(temporary)
        for source in sources:
            svg_text = source.read_text(encoding="utf-8")
            width, height = _view_box(svg_text, source)

            for theme in ("light", "dark"):
                themed_svg = temporary_dir / f"{source.stem}-{theme}.svg"
                themed_svg.write_text(
                    _themed_svg(svg_text, source, dark=theme == "dark"),
                    encoding="utf-8",
                )
                wrapper = temporary_dir / f"{source.stem}-{theme}.html"
                wrapper.write_text(
                    _wrapper(themed_svg, width, height, dark=theme == "dark"),
                    encoding="utf-8",
                )

                output = IMAGE_DIR / f"{source.stem}-{theme}.png"
                temporary_output = temporary_dir / output.name
                _render(
                    wrapper,
                    temporary_output,
                    width,
                    height,
                    temporary_dir / "chromium-profile",
                )
                _validate_png(temporary_output, width, height)
                temporary_output.replace(output)
                print(
                    f"rendered {output.relative_to(ROOT)} "
                    f"({width * SCALE}x{height * SCALE}, {output.stat().st_size} bytes)"
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
