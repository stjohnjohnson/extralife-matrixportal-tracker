"""Render MatrixPortal display states locally with the bundled BDF font."""

import struct
import sys
import zlib
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.append(str(ROOT))

from lib_display import (  # noqa: E402
    _pair_adjusted_text,
    display_colors,
    display_text,
    render_state,
    two_line_positions,
)

BLACK = (0x00, 0x00, 0x00)
TEAL = (0x1A, 0xC1, 0xDD)
GREEN = (0x85, 0xFF, 0x00)
GOLD = (0xFF, 0xB0, 0x00)


class Glyph:
    def __init__(self, *, width, height, dx, dy, shift_x, bitmap_rows):
        self.width = width
        self.height = height
        self.dx = dx
        self.dy = dy
        self.shift_x = shift_x
        self.bitmap_rows = tuple(bitmap_rows)


class BdfFont:
    def __init__(self, *, ascent, glyphs):
        self.ascent = ascent
        self.glyphs = glyphs


class TextLayout:
    def __init__(self, *, bounding_box, placements):
        self.bounding_box = bounding_box
        self.placements = tuple(placements)


def load_bdf(path):
    """Parse the BDF fields required by the display preview renderer."""
    ascent = None
    glyphs = {}
    current = None
    reading_bitmap = False

    for line in Path(path).read_text().splitlines():
        if line.startswith("FONT_ASCENT "):
            ascent = int(line.split()[1])
        elif line.startswith("STARTCHAR "):
            current = {"bitmap_rows": []}
            reading_bitmap = False
        elif line == "BITMAP" and current is not None:
            reading_bitmap = True
        elif line == "ENDCHAR" and current is not None:
            encoding = current.get("encoding", -1)
            if encoding >= 0:
                width, height, dx, dy = current["bbx"]
                glyphs[chr(encoding)] = Glyph(
                    width=width,
                    height=height,
                    dx=dx,
                    dy=dy,
                    shift_x=current["shift_x"],
                    bitmap_rows=current["bitmap_rows"],
                )
            current = None
            reading_bitmap = False
        elif current is not None and reading_bitmap:
            current["bitmap_rows"].append(line)
        elif current is not None and line.startswith("ENCODING "):
            current["encoding"] = int(line.split()[1])
        elif current is not None and line.startswith("DWIDTH "):
            current["shift_x"] = int(line.split()[1])
        elif current is not None and line.startswith("BBX "):
            current["bbx"] = tuple(int(value) for value in line.split()[1:])

    if ascent is None:
        raise ValueError("BDF font does not define FONT_ASCENT")
    return BdfFont(ascent=ascent, glyphs=glyphs)


def layout_text(font, text):
    """Lay out text using Adafruit Display Text's left-to-right equations."""
    pen_x = 0
    top = 0
    right = 0
    bottom = 0
    placements = []
    y_offset = font.ascent // 2

    for character in text:
        glyph = font.glyphs.get(character)
        if glyph is None:
            continue
        top = min(top, -glyph.height - glyph.dy + y_offset)
        bottom = max(bottom, -glyph.dy + y_offset)
        right = max(
            right,
            pen_x + glyph.shift_x,
            pen_x + glyph.width + glyph.dx,
        )
        glyph_x = pen_x + glyph.dx
        glyph_y = -glyph.height - glyph.dy + y_offset
        placements.append((glyph, glyph_x, glyph_y))
        pen_x += glyph.shift_x

    return TextLayout(
        bounding_box=(0, top, right, bottom - top),
        placements=placements,
    )


def preview_states():
    """Return deterministic examples of every rotating card in every phase."""
    target = datetime(2026, 11, 7, 16, 30, 0)
    phase_samples = (
        ("pre", target - timedelta(days=100), 5),
        ("countdown", target - timedelta(hours=999, minutes=30), 4),
        ("game_day", target + timedelta(hours=12, minutes=34, seconds=56), 1),
        ("post", target + timedelta(hours=26), 4),
    )
    states = {}
    for phase, now, card_count in phase_samples:
        states[phase] = [
            render_state(
                target_date=target,
                now=now,
                total_raised=1234.0,
                hide_before=1000,
                hide_after=26,
                last_raised=28783,
                last_year=2025,
                lifetime_raised=88488,
                rotation_elapsed=slot * 15,
            )
            for slot in range(card_count)
        ]
    return states


def _draw_text(pixels, layout, origin, color):
    origin_x, origin_y = origin
    for glyph, glyph_x, glyph_y in layout.placements:
        for row_index, row_hex in enumerate(glyph.bitmap_rows):
            row_bits = int(row_hex, 16)
            padded_width = len(row_hex) * 4
            for column in range(glyph.width):
                mask = 1 << (padded_width - column - 1)
                if not row_bits & mask:
                    continue
                x = origin_x + glyph_x + column
                y = origin_y + glyph_y + row_index
                if 0 <= x < 64 and 0 <= y < 32:
                    pixels[y][x] = color


def render_card(font, state, text_transform=display_text):
    """Render one production display state into a 64x32 RGB pixel grid."""
    top_text = text_transform(state.top_text)
    bottom_text = text_transform(state.bottom_text)
    top_layout = layout_text(font, top_text)
    bottom_layout = layout_text(font, bottom_text)
    top_position, bottom_position = two_line_positions(
        top_layout.bounding_box,
        bottom_layout.bounding_box,
        display_width=64,
        display_height=32,
        top_align=state.top_align,
        bottom_align=state.bottom_align,
    )
    top_color, bottom_color = display_colors(
        state,
        context_color=TEAL,
        money_color=GREEN,
        accent_color=GOLD,
    )
    pixels = [[BLACK for _ in range(64)] for _ in range(32)]
    _draw_text(pixels, top_layout, top_position, top_color)
    _draw_text(pixels, bottom_layout, bottom_position, bottom_color)
    return pixels


def _png_chunk(chunk_type, data):
    payload = chunk_type + data
    return (
        struct.pack(">I", len(data))
        + payload
        + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)
    )


def write_png(path, pixels):
    """Write an RGB pixel grid as a dependency-free PNG file."""
    height = len(pixels)
    width = len(pixels[0])
    raw_rows = []
    for row in pixels:
        raw_rows.append(b"\x00" + bytes(channel for pixel in row for channel in pixel))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += _png_chunk(b"IHDR", ihdr)
    png += _png_chunk(b"IDAT", zlib.compress(b"".join(raw_rows)))
    png += _png_chunk(b"IEND", b"")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def _scale_pixels(pixels, scale):
    scaled = []
    for row in pixels:
        scaled_row = [pixel for pixel in row for _ in range(scale)]
        for _ in range(scale):
            scaled.append(list(scaled_row))
    return scaled


def _horizontal_strip(images, gap):
    height = len(images[0])
    width = sum(len(image[0]) for image in images) + gap * (len(images) - 1)
    strip = [[BLACK for _ in range(width)] for _ in range(height)]
    left = 0
    for image in images:
        image_width = len(image[0])
        for y, row in enumerate(image):
            strip[y][left : left + image_width] = row
        left += image_width + gap
    return strip


def _vertical_overview(images, gap):
    width = max(len(image[0]) for image in images)
    height = sum(len(image) for image in images) + gap * (len(images) - 1)
    overview = [[BLACK for _ in range(width)] for _ in range(height)]
    top = 0
    for image in images:
        image_width = len(image[0])
        left = (width - image_width) // 2
        for y, row in enumerate(image):
            overview[top + y][left : left + image_width] = row
        top += len(image) + gap
    return overview


def render_previews(output_dir):
    """Write exact cards, enlarged phase strips, and a combined overview."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    font = load_bdf(ROOT / "Micro5-Regular-21.bdf")
    states = preview_states()
    written = []
    phase_strips = []

    for phase, cards in states.items():
        file_phase = phase.replace("_", "-")
        enlarged_cards = []
        for slot, state in enumerate(cards, start=1):
            pixels = render_card(font, state)
            card_path = output_dir / f"{file_phase}-{slot:02d}.png"
            write_png(card_path, pixels)
            written.append(card_path)
            enlarged_cards.append(_scale_pixels(pixels, 8))

        strip = _horizontal_strip(enlarged_cards, gap=16)
        strip_path = output_dir / f"{file_phase}-strip.png"
        write_png(strip_path, strip)
        written.append(strip_path)
        phase_strips.append(strip)

    overview_path = output_dir / "all-phases.png"
    write_png(overview_path, _vertical_overview(phase_strips, gap=16))
    written.append(overview_path)

    url_state = states["pre"][4]
    before = _scale_pixels(
        render_card(font, url_state, text_transform=_pair_adjusted_text),
        8,
    )
    after = _scale_pixels(render_card(font, url_state), 8)
    comparison_path = output_dir / "at-spacing-comparison.png"
    write_png(comparison_path, _horizontal_strip((before, after), gap=16))
    written.append(comparison_path)
    return written


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: render_display_previews.py OUTPUT_DIRECTORY")
    for path in render_previews(Path(sys.argv[1])):
        print(path)


if __name__ == "__main__":
    main()
