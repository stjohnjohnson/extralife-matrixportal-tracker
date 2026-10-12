"""Check production animation pixels against the independent BDF renderer."""

import tempfile
import unittest

from lib_celebration import paint_text
from lib_display import display_colors, display_text, two_line_positions
from tools.render_display_previews import (
    BLACK,
    GOLD,
    GREEN,
    ROOT,
    TEAL,
    layout_text,
    load_bdf,
    preview_states,
    render_card,
    render_celebration_frame,
    render_celebration_previews,
)


class CelebrationPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.font = load_bdf(ROOT / "Micro5-Regular-21.bdf")

    def test_snapshot_matches_every_normal_card_including_private_glyphs(self):
        palette = (BLACK, TEAL, GREEN, GOLD)
        for states in preview_states().values():
            for state in states:
                with self.subTest(state=state):
                    texts = (
                        display_text(state.top_text),
                        display_text(state.bottom_text),
                    )
                    boxes = [
                        layout_text(self.font, text).bounding_box for text in texts
                    ]
                    positions = two_line_positions(
                        *boxes,
                        display_width=64,
                        display_height=32,
                        top_align=state.top_align,
                        bottom_align=state.bottom_align,
                    )
                    colors = display_colors(
                        state, context_color=1, money_color=2, accent_color=3
                    )
                    bitmap = bytearray(2048)
                    for text, position, color in zip(texts, positions, colors):
                        paint_text(bitmap, self.font, text, position, color)
                    pixels = [
                        [palette[value] for value in bitmap[row * 64 : (row + 1) * 64]]
                        for row in range(32)
                    ]
                    self.assertEqual(pixels, render_card(self.font, state))

    def test_hold_uses_blue_name_and_green_amount_without_gold(self):
        pixels = render_celebration_frame(self.font, "$25.50", "SAM", 4)
        self.assertEqual({p for row in pixels[:16] for p in row}, {BLACK, GREEN})
        self.assertEqual({p for row in pixels[16:] for p in row}, {BLACK, TEAL})

    def test_entrance_and_return_match_normal_display_exactly(self):
        normal = render_card(self.font, preview_states()["countdown"][0])
        self.assertEqual(render_celebration_frame(self.font, "$25", "SAM", 0), normal)
        self.assertEqual(render_celebration_frame(self.font, "$25", "SAM", 9), normal)

    def test_name_pan_changes_name_pixels_while_amount_stays_fixed(self):
        before = render_celebration_frame(self.font, "$25", "ALEX JOHNSON", 3.49)
        after = render_celebration_frame(self.font, "$25", "ALEX JOHNSON", 4)
        self.assertEqual(before[:16], after[:16])
        self.assertNotEqual(before[16:], after[16:])

    def test_preview_writes_animation_and_privacy_sheets(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = render_celebration_previews(directory)
            self.assertEqual(
                {p.name for p in paths},
                {
                    "celebration-sequence.png",
                    "celebration-long-name.png",
                    "celebration-private.png",
                },
            )
            self.assertTrue(all(p.read_bytes().startswith(b"\x89PNG") for p in paths))
