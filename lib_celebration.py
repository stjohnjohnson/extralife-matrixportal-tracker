"""Arcade donation timing and indexed pixels, without hardware imports."""

import math

from lib_display import ALIGN_CENTER, two_line_positions

ENTRANCE_SECONDS = 1.8
SPARKLE_SECONDS = 1.7
CARD_SECONDS = 5.5
EXIT_SECONDS = 0.9
GAP_SECONDS = 2
SCROLL_SPEED = 18
READ_PAUSE = 1.1
END_PAUSE = 1.5
FRAME_SECONDS = 0.05


def _clamp(value):
    return max(0.0, min(1.0, value))


class Celebration:
    """An amount and name get separate scrolling beats when both overflow."""

    def __init__(self, top_box, bottom_box):
        self.top_box = top_box
        self.bottom_box = bottom_box
        self.origins = two_line_positions(
            top_box,
            bottom_box,
            display_width=64,
            display_height=32,
            top_align=ALIGN_CENTER,
            bottom_align=ALIGN_CENTER,
        )
        self.top_overflow = max(0, top_box[2] - 62)
        self.bottom_overflow = max(0, bottom_box[2] - 62)
        self.top_start = max(READ_PAUSE, SPARKLE_SECONDS)
        self.top_end = self.top_start + self.top_overflow / SCROLL_SPEED
        self.bottom_start = (
            self.top_end + END_PAUSE if self.top_overflow else self.top_start
        )
        self.bottom_end = self.bottom_start + self.bottom_overflow / SCROLL_SPEED
        reading_end = self.bottom_end if self.bottom_overflow else self.top_end
        self.exit_at = ENTRANCE_SECONDS + max(CARD_SECONDS, reading_end + END_PAUSE)
        self.duration = self.exit_at + EXIT_SECONDS

    def stage(self, elapsed):
        if elapsed + 0.000001 >= self.duration:
            return "done"
        if elapsed + 0.000001 >= self.exit_at:
            return "exit"
        if elapsed < ENTRANCE_SECONDS:
            return "entrance"
        card_elapsed = elapsed - ENTRANCE_SECONDS
        if card_elapsed < SPARKLE_SECONDS:
            return "sparkles"
        if self.top_overflow and self.top_start <= card_elapsed < self.top_end:
            return "scroll_amount"
        if self.bottom_overflow and self.bottom_start <= card_elapsed < self.bottom_end:
            return "scroll_name"
        return "hold"

    def positions(self, elapsed):
        card_elapsed = max(0, elapsed - ENTRANCE_SECONDS)
        positions = []
        for box, origin, overflow, start in (
            (self.top_box, self.origins[0], self.top_overflow, self.top_start),
            (self.bottom_box, self.origins[1], self.bottom_overflow, self.bottom_start),
        ):
            x, y = origin
            if overflow:
                offset = min(overflow, int(max(0, card_elapsed - start) * SCROLL_SPEED))
                x = 1 - box[0] - offset
            positions.append((x, y))
        return positions[0], positions[1]


def star_thresholds():
    """Precompute the eight-point reveal; frame drawing needs no trigonometry."""
    thresholds = bytearray(64 * 32)
    for y in range(32):
        for x in range(64):
            dx, dy = x - 31.5, y - 15.5
            shape = 0.34 + 0.66 * abs(math.cos(math.atan2(dy, dx) * 4))
            thresholds[y * 64 + x] = min(
                255, int(2 * math.sqrt(dx * dx + dy * dy) / shape)
            )
    return thresholds


def starburst_frame(target, old, new, thresholds, progress):
    """Reveal new pixels inside the growing star, with a narrow gold edge."""
    progress = _clamp(progress)
    radius = 250 * progress * progress * (3 - 2 * progress)
    limit = -1 if progress <= 0 else 255 if progress >= 1 else int(radius)
    edge = 0.02 < progress < 0.96
    lower = math.ceil(radius - 1.5) if edge else -1
    upper = math.floor(radius + 1.5) if edge else -1
    for index in range(2048):
        distance = thresholds[index]
        if lower <= distance <= upper:
            target[index] = 3
        elif distance <= limit:
            target[index] = new[index]
        else:
            target[index] = old[index]


def slide_frame(target, old, new, progress):
    """Slide the donation up while the current normal card enters below it."""
    offset = int(32 * _clamp(progress) + 0.5)
    for y in range(32):
        source_y = y + offset
        source = old if source_y < 32 else new
        source_row = (source_y % 32) * 64
        for x in range(64):
            target[y * 64 + x] = source[source_row + x]


def sparkle_pixels(elapsed):
    """Small edge sparkles finish before either text line starts scrolling."""
    elapsed /= 2
    for x, y, delay in ((6, 1, 0), (55, 1, 0.16), (4, 30, 0.34), (59, 30, 0.5)):
        age = elapsed - delay
        if 0 <= age < 0.32:
            yield x, y
            if age < 0.13:
                yield x - 1, y
                yield x + 1, y
                yield x, y - 1
                yield x, y + 1


def paint_text(bitmap, font, text, origin, color_index):
    """Snapshot an LTR BDF label into a 64x32 indexed bitmap."""
    pen_x, baseline = origin
    y_offset = font.ascent // 2
    for character in text:
        glyph = font.get_glyph(ord(character))
        if glyph is None:
            continue
        left = pen_x + glyph.dx
        top = baseline - glyph.height - glyph.dy + y_offset
        if left < 64 and left + glyph.width > 0:
            for row in range(glyph.height):
                y = top + row
                if not 0 <= y < 32:
                    continue
                for column in range(glyph.width):
                    x = left + column
                    if 0 <= x < 64 and glyph.bitmap[column, row]:
                        bitmap[y * 64 + x] = color_index
        pen_x += glyph.shift_x
