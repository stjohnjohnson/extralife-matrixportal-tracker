"""Observable timing and pixels for the arcade donation celebration."""

import unittest

from lib_celebration import (
    Celebration,
    paint_text,
    slide_frame,
    sparkle_pixels,
    star_thresholds,
    starburst_frame,
)
from lib_display import RotationClock
from tools.render_display_previews import ROOT, load_bdf


class CelebrationTimingTests(unittest.TestCase):
    def test_short_card_settles_then_exits_and_finishes(self):
        celebration = Celebration((0, -5, 26, 14), (0, -3, 30, 10))
        for time, stage in (
            (0, "entrance"),
            (0.9, "entrance"),
            (1.8, "sparkles"),
            (3.5, "hold"),
            (7.3, "exit"),
            (8.2, "done"),
        ):
            with self.subTest(time=time):
                self.assertEqual(celebration.stage(time), stage)
        self.assertEqual(celebration.positions(2), ((19, 7), (17, 22)))

    def test_name_scroll_waits_for_sparkles_and_amount_stays_stationary(self):
        celebration = Celebration((0, -5, 26, 14), (0, -3, 89, 10))
        self.assertEqual(celebration.positions(3.49), ((19, 7), (1, 22)))
        self.assertEqual(celebration.stage(3.9), "scroll_name")
        self.assertEqual(celebration.positions(3.9)[0], (19, 7))
        self.assertEqual(celebration.positions(3.9)[1][0], -6)
        self.assertEqual(celebration.positions(6)[1], (-26, 22))

    def test_very_long_name_extends_reading_time_and_reaches_last_letter(self):
        celebration = Celebration((0, -5, 26, 14), (0, -3, 350, 10))
        self.assertGreater(celebration.duration, 19)
        self.assertEqual(
            celebration.positions(celebration.exit_at - 0.1)[1], (-287, 22)
        )

    def test_oversized_amount_and_name_scroll_in_separate_beats(self):
        celebration = Celebration((0, -5, 110, 14), (0, -3, 89, 10))
        self.assertEqual(celebration.stage(3.9), "scroll_amount")
        self.assertEqual(celebration.positions(3.9)[1], (1, 22))
        self.assertEqual(celebration.stage(8), "scroll_name")
        self.assertEqual(celebration.positions(8)[0], (-47, 7))


class RotationPauseTests(unittest.TestCase):
    def test_return_preserves_remaining_dwell_time_but_timer_clock_is_separate(self):
        clock = RotationClock()
        self.assertEqual(clock.update("countdown", 0), 0)
        self.assertEqual(clock.update("countdown", 10, paused=True), 10)
        self.assertEqual(clock.update("countdown", 16, paused=True), 10)
        self.assertEqual(clock.update("countdown", 17, paused=False), 10)
        self.assertEqual(clock.update("countdown", 19), 12)

    def test_phase_change_during_celebration_returns_to_new_phase_first_card(self):
        clock = RotationClock()
        clock.update("countdown", 0)
        clock.update("countdown", 10, paused=True)
        self.assertEqual(clock.update("game_day", 12, paused=True), 0)
        self.assertEqual(clock.update("game_day", 17), 0)


class CelebrationPixelTests(unittest.TestCase):
    def test_starburst_preserves_old_outside_and_reveals_new_inside(self):
        old, new, target = bytearray([1] * 2048), bytearray([2] * 2048), bytearray(2048)
        mask = star_thresholds()
        self.assertEqual(len(mask), 2048)
        starburst_frame(target, old, new, mask, 0)
        self.assertEqual(target, old)
        starburst_frame(target, old, new, mask, 0.15)
        self.assertEqual(target[16 * 64 + 32], 2)
        self.assertEqual(target[0], 1)
        self.assertIn(3, target)
        starburst_frame(target, old, new, mask, 1)
        self.assertEqual(target, new)

    def test_slide_replaces_card_with_normal_display_at_completion(self):
        old, new, target = bytearray([2] * 2048), bytearray([1] * 2048), bytearray(2048)
        slide_frame(target, old, new, 0.5)
        self.assertEqual(target[:1024], bytearray([2] * 1024))
        self.assertEqual(target[1024:], bytearray([1] * 1024))
        slide_frame(target, old, new, 1)
        self.assertEqual(target, new)

    def test_sparkles_stay_at_edges_and_finish_before_scrolling(self):
        pixels = list(sparkle_pixels(0.1))
        self.assertTrue(pixels)
        self.assertTrue(all(0 <= x < 64 and 0 <= y < 32 for x, y in pixels))
        self.assertTrue(all(y <= 2 or y >= 29 for _, y in pixels))
        self.assertEqual(
            set(sparkle_pixels(0.2)), {(6, 1), (5, 1), (7, 1), (6, 0), (6, 2)}
        )
        self.assertTrue(list(sparkle_pixels(1.5)))
        self.assertEqual(list(sparkle_pixels(1.7)), [])

    def test_snapshot_rasterizer_matches_actual_bdf_money_glyphs(self):
        font = load_bdf(ROOT / "Micro5-Regular-21.bdf")
        bitmap = bytearray(2048)
        paint_text(bitmap, font, "$25", (19, 7), 2)
        # Hand-checked dollar at visible x=19, y=2; green pixels stay in top line.
        self.assertTrue(any(bitmap))
        lit = [(i % 64, i // 64) for i, value in enumerate(bitmap) if value]
        self.assertEqual(min(y for _, y in lit), 2)
        self.assertEqual(max(y for _, y in lit), 15)
        self.assertTrue(all(value in (0, 2) for value in bitmap))
