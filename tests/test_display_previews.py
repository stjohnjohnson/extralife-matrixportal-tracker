import struct
import tempfile
import unittest
from pathlib import Path

from lib_display import (
    ALIGN_CENTER,
    KERNED_T,
    URL_GLYPHS,
    URL_J,
    URL_TEXT,
    _pair_adjusted_text,
    display_text,
    two_line_positions,
)
from tools.render_display_previews import (
    BLACK,
    GOLD,
    TEAL,
    layout_text,
    load_bdf,
    preview_states,
    render_card,
    render_previews,
)

FONT_PATH = Path(__file__).parents[1] / "Micro5-Regular-21.bdf"


class BdfPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.font = load_bdf(FONT_PATH)

    def test_parses_adjusted_font_metrics(self):
        self.assertEqual(self.font.ascent, 15)
        self.assertEqual(self.font.glyphs["J"].shift_x, 5)
        self.assertEqual(self.font.glyphs["T"].shift_x, 7)
        standard_t = self.font.glyphs["T"]
        kerned_t = self.font.glyphs[KERNED_T]
        self.assertEqual(kerned_t.bitmap_rows, standard_t.bitmap_rows)
        self.assertEqual(kerned_t.width, standard_t.width)
        self.assertEqual(kerned_t.height, standard_t.height)
        self.assertEqual(kerned_t.dy, standard_t.dy)
        self.assertEqual(kerned_t.shift_x, standard_t.shift_x)
        self.assertEqual(kerned_t.dx, standard_t.dx - 1)

        url_glyphs = zip("S.ACH", URL_GLYPHS, (7, 4, 7, 5, 6))
        self.assertEqual(self.font.glyphs["."].shift_x, 4)
        for source_character, private_character, advance in url_glyphs:
            with self.subTest(source_character=source_character):
                source = self.font.glyphs[source_character]
                private = self.font.glyphs[private_character]
                self.assertEqual(private.bitmap_rows, source.bitmap_rows)
                self.assertEqual(private.width, source.width)
                self.assertEqual(private.height, source.height)
                self.assertEqual(private.dx, source.dx)
                self.assertEqual(private.dy, source.dy)
                self.assertEqual(private.shift_x, advance)

        source_j = self.font.glyphs["J"]
        url_j = self.font.glyphs[URL_J]
        self.assertEqual(url_j.bitmap_rows, source_j.bitmap_rows)
        self.assertEqual(url_j.width, source_j.width)
        self.assertEqual(url_j.height, source_j.height)
        self.assertEqual(url_j.dx, source_j.dx)
        self.assertEqual(url_j.dy, source_j.dy)
        self.assertEqual(url_j.shift_x, source_j.shift_x + 1)

    def test_layout_matches_adafruit_ltr_bounds(self):
        context = layout_text(self.font, "RAISED")
        money = layout_text(self.font, "$28,783")
        self.assertEqual(context.bounding_box[1:], (-3, 44, 10))
        self.assertEqual(money.bounding_box[1], -5)
        self.assertEqual(money.bounding_box[3], 14)


class RenderPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.font = load_bdf(FONT_PATH)

    def test_preview_states_cover_every_phase_card(self):
        states = preview_states()
        self.assertEqual(
            {phase: len(cards) for phase, cards in states.items()},
            {"pre": 5, "countdown": 4, "game_day": 1, "post": 4},
        )
        for cards in states.values():
            for state in cards:
                self.assertEqual(state.top_align, ALIGN_CENTER)
                self.assertEqual(state.bottom_align, ALIGN_CENTER)

    def test_rendered_context_card_uses_exact_colors_and_dimensions(self):
        state = preview_states()["pre"][2]
        pixels = render_card(self.font, state)
        self.assertEqual((len(pixels[0]), len(pixels)), (64, 32))
        colors = {pixel for row in pixels for pixel in row}
        self.assertEqual(colors, {BLACK, TEAL, GOLD})

    def test_url_has_balanced_period_gaps_and_margins(self):
        layout = layout_text(self.font, display_text(URL_TEXT))
        self.assertEqual(layout.bounding_box[2], 60)

        visible_bounds = []
        for glyph, glyph_x, _ in layout.placements:
            columns = []
            for row_hex in glyph.bitmap_rows:
                bits = int(row_hex, 16)
                padded_width = len(row_hex) * 4
                columns.extend(
                    column
                    for column in range(glyph.width)
                    if bits & (1 << (padded_width - column - 1))
                )
            visible_bounds.append(
                (glyph_x + min(columns) + 2, glyph_x + max(columns) + 2)
            )

        self.assertEqual(visible_bounds[0][0], 2)
        self.assertEqual(visible_bounds[-1][1], 61)
        gaps = [
            following[0] - current[1] - 1
            for current, following in zip(visible_bounds, visible_bounds[1:])
        ]
        self.assertEqual(gaps, [1, 1, 2, 2, 1, 1, 1, 1])

    def test_at_pair_moves_only_the_t_pixels_left(self):
        before = layout_text(self.font, "AT")
        after = layout_text(self.font, display_text("AT"))
        self.assertEqual(before.bounding_box, after.bounding_box)
        self.assertEqual(before.placements[0][1], after.placements[0][1])
        self.assertEqual(before.placements[1][1] - 1, after.placements[1][1])

    def test_url_comparison_uses_current_and_selected_transforms(self):
        state = preview_states()["pre"][4]
        current = render_card(self.font, state, text_transform=_pair_adjusted_text)
        selected = render_card(self.font, state)
        current_columns = {
            x for row in current for x, pixel in enumerate(row) if pixel == GOLD
        }
        selected_columns = {
            x for row in selected for x, pixel in enumerate(row) if pixel == GOLD
        }
        self.assertEqual((min(current_columns), max(current_columns)), (0, 61))
        self.assertEqual((min(selected_columns), max(selected_columns)), (2, 61))

    def test_context_lines_are_centered_with_three_pixel_gap(self):
        state = preview_states()["pre"][2]
        top = layout_text(self.font, state.top_text)
        bottom = layout_text(self.font, state.bottom_text)
        positions = two_line_positions(
            top.bounding_box,
            bottom.bounding_box,
            display_width=64,
            display_height=32,
            top_align=state.top_align,
            bottom_align=state.bottom_align,
        )
        self.assertEqual(positions[0][0] + top.bounding_box[0], 10)
        self.assertEqual(positions[1][0] + bottom.bounding_box[0], 2)
        top_bottom = positions[0][1] + top.bounding_box[1] + top.bounding_box[3]
        bottom_top = positions[1][1] + bottom.bounding_box[1]
        self.assertEqual(bottom_top - top_bottom, 3)


class PngOutputTests(unittest.TestCase):
    def test_render_previews_writes_exact_cards_and_sheets(self):
        exact_names = [f"pre-{slot:02d}.png" for slot in range(1, 6)]
        exact_names += [f"countdown-{slot:02d}.png" for slot in range(1, 5)]
        exact_names += ["game-day-01.png"]
        exact_names += [f"post-{slot:02d}.png" for slot in range(1, 5)]
        sheet_names = [
            "pre-strip.png",
            "countdown-strip.png",
            "game-day-strip.png",
            "post-strip.png",
            "all-phases.png",
            "at-spacing-comparison.png",
        ]

        with tempfile.TemporaryDirectory() as directory:
            paths = render_previews(Path(directory))
            self.assertEqual(
                {path.name for path in paths},
                set(exact_names + sheet_names),
            )

            for name in exact_names:
                data = (Path(directory) / name).read_bytes()
                self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(data[12:16], b"IHDR")
                width, height, bit_depth, color_type, _, _, _ = struct.unpack(
                    ">IIBBBBB", data[16:29]
                )
                self.assertEqual((width, height), (64, 32))
                self.assertEqual((bit_depth, color_type), (8, 2))


if __name__ == "__main__":
    unittest.main()
