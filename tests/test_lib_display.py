import unittest
from datetime import datetime, timedelta

from lib_display import (
    ALIGN_CENTER,
    ALIGN_LEFT,
    ALIGN_RIGHT,
    KERNED_T,
    PHASE_COUNTDOWN,
    PHASE_GAME_DAY,
    PHASE_POST,
    PHASE_PRE,
    URL_GLYPH_TEXT,
    URL_J,
    URL_TEXT,
    DisplayState,
    display_colors,
    display_phase,
    display_text,
    label_x,
    render_state,
    single_line_position,
    track_rotation,
    two_line_positions,
)

TARGET = datetime(2026, 11, 7, 16, 30, 0)


class DisplayTextTests(unittest.TestCase):
    def test_replaces_only_t_directly_after_a(self):
        self.assertEqual(display_text(URL_TEXT), URL_GLYPH_TEXT)
        self.assertIn(URL_J, display_text(URL_TEXT))
        self.assertNotIn(URL_J, display_text("STJ.WATCH!"))
        self.assertEqual(display_text("MORE AT"), f"MORE A{KERNED_T}")
        self.assertEqual(display_text("ATT AT"), f"A{KERNED_T}T A{KERNED_T}")
        self.assertEqual(display_text("STJ.WATCH!"), f"STJ.WA{KERNED_T}CH!")

    def test_leaves_other_a_and_t_text_unchanged(self):
        for value in ("ALL", "ALL TIME", "TO GO", "RAISED"):
            with self.subTest(value=value):
                self.assertEqual(display_text(value), value)


class DisplayPhaseTests(unittest.TestCase):
    def phase_at(self, now):
        return display_phase(
            target_date=TARGET,
            now=now,
            hide_before=1000,
            hide_after=26,
        )

    def test_exactly_1000_hours_is_pre_countdown(self):
        self.assertEqual(
            self.phase_at(TARGET - timedelta(hours=1000)),
            PHASE_PRE,
        )

    def test_one_second_below_1000_hours_is_countdown(self):
        self.assertEqual(
            self.phase_at(TARGET - timedelta(hours=1000) + timedelta(seconds=1)),
            PHASE_COUNTDOWN,
        )

    def test_target_instant_starts_game_day(self):
        self.assertEqual(self.phase_at(TARGET), PHASE_GAME_DAY)

    def test_countup_continues_through_25_hours(self):
        self.assertEqual(
            self.phase_at(TARGET + timedelta(hours=25, minutes=59, seconds=59)),
            PHASE_GAME_DAY,
        )

    def test_exactly_26_hours_is_post_event(self):
        self.assertEqual(
            self.phase_at(TARGET + timedelta(hours=26)),
            PHASE_POST,
        )

    def test_rotation_resets_only_when_phase_changes(self):
        active, started, elapsed = track_rotation(
            current_phase=PHASE_PRE,
            monotonic_now=100.0,
            active_phase=None,
            phase_started_at=None,
        )
        self.assertEqual((active, started, elapsed), (PHASE_PRE, 100.0, 0.0))

        active, started, elapsed = track_rotation(
            current_phase=PHASE_PRE,
            monotonic_now=114.5,
            active_phase=active,
            phase_started_at=started,
        )
        self.assertEqual((active, started, elapsed), (PHASE_PRE, 100.0, 14.5))

        active, started, elapsed = track_rotation(
            current_phase=PHASE_COUNTDOWN,
            monotonic_now=120.0,
            active_phase=active,
            phase_started_at=started,
        )
        self.assertEqual((active, started, elapsed), (PHASE_COUNTDOWN, 120.0, 0.0))


class LabelPositionTests(unittest.TestCase):
    def test_horizontal_positions_align_visible_bounds(self):
        box = (-1, 0, 20, 10)
        self.assertEqual(label_x(box, display_width=64, alignment=ALIGN_LEFT), 2)
        self.assertEqual(label_x(box, display_width=64, alignment=ALIGN_CENTER), 23)
        self.assertEqual(label_x(box, display_width=64, alignment=ALIGN_RIGHT), 44)

    def test_full_width_text_falls_back_to_center(self):
        box = (0, 0, 64, 10)
        self.assertEqual(label_x(box, display_width=64, alignment=ALIGN_RIGHT), 0)

    def test_context_pair_has_three_pixel_visible_gap(self):
        positions = two_line_positions(
            (0, 0, 44, 10),
            (0, 0, 59, 10),
            display_width=64,
            display_height=32,
            top_align=ALIGN_LEFT,
            bottom_align=ALIGN_RIGHT,
        )
        self.assertEqual(positions, ((1, 4), (4, 17)))

    def test_money_pair_has_same_three_pixel_visible_gap(self):
        positions = two_line_positions(
            (0, -2, 60, 14),
            (0, 0, 50, 10),
            display_width=64,
            display_height=32,
            top_align=ALIGN_CENTER,
            bottom_align=ALIGN_CENTER,
        )
        self.assertEqual(positions, ((2, 4), (7, 19)))

    def test_single_line_centers_visible_bounds(self):
        self.assertEqual(
            single_line_position(
                (-1, -2, 60, 14),
                display_width=64,
                display_height=32,
            ),
            (3, 11),
        )


class RenderStateTests(unittest.TestCase):
    def render(
        self,
        now,
        slot=0,
        total_raised=1234.0,
        rotation_elapsed=None,
    ):
        if rotation_elapsed is None:
            rotation_elapsed = slot * 15
        return render_state(
            target_date=TARGET,
            now=now,
            total_raised=total_raised,
            hide_before=1000,
            hide_after=26,
            last_raised=28783,
            last_year=2025,
            lifetime_raised=88488,
            rotation_elapsed=rotation_elapsed,
        )

    def assert_card(
        self,
        state,
        top,
        bottom,
        top_money=False,
        bottom_money=False,
        top_accent=False,
        bottom_accent=False,
        top_align=ALIGN_CENTER,
        bottom_align=ALIGN_CENTER,
    ):
        self.assertEqual((state.top_text, state.bottom_text), (top, bottom))
        self.assertEqual(state.top_is_money, top_money)
        self.assertEqual(state.bottom_is_money, bottom_money)
        self.assertEqual(state.top_is_accent, top_accent)
        self.assertEqual(state.bottom_is_accent, bottom_accent)
        self.assertEqual(state.top_align, top_align)
        self.assertEqual(state.bottom_align, bottom_align)

    def test_pre_countdown_rotation(self):
        now = TARGET - timedelta(days=100)
        expected = [
            ("$28,783", "IN 2025", True, False),
            ("$89,722", "ALL TIME", True, False),
            ("RAISED", "FOR UCSF", False, False, False, True),
            ("100 DAYS", "TO GO", False, False, True, False),
            ("MORE AT", "STJ.WATCH", False, False, False, True),
        ]
        for slot, card in enumerate(expected):
            with self.subTest(slot=slot):
                self.assert_card(self.render(now, slot), *card)
        self.assert_card(self.render(now, 5), *expected[0])

    def test_partial_pre_countdown_day_rounds_up(self):
        state = self.render(TARGET - timedelta(days=100, seconds=1), 3)
        self.assertEqual(state.top_text, "101 DAYS")

    def test_card_changes_at_exactly_15_seconds(self):
        now = TARGET - timedelta(days=100)
        before = self.render(now, rotation_elapsed=14.999)
        at_boundary = self.render(now, rotation_elapsed=15.0)
        self.assertEqual(before.bottom_text, "IN 2025")
        self.assertEqual(at_boundary.bottom_text, "ALL TIME")

    def test_countdown_rotation_prioritizes_timer(self):
        now = TARGET - timedelta(hours=999, minutes=30)
        expected = [
            ("999:30:00", "$1,234", False, True),
            ("RAISED", "FOR UCSF", False, False, False, True),
            ("999:30:00", "$1,234", False, True),
            ("MORE AT", "STJ.WATCH", False, False, False, True),
        ]
        for slot, card in enumerate(expected):
            with self.subTest(slot=slot):
                self.assert_card(self.render(now, slot), *card)

    def test_game_day_does_not_rotate(self):
        now = TARGET + timedelta(hours=12, minutes=34, seconds=56)
        first = self.render(now, 0)
        later = self.render(now, 99)
        self.assert_card(first, "12:34:56", "$1,234", False, True)
        self.assert_card(later, "12:34:56", "$1,234", False, True)
        self.assertEqual(first.top_align, ALIGN_CENTER)
        self.assertEqual(first.bottom_align, ALIGN_CENTER)

    def test_every_production_card_is_centered(self):
        phase_slots = (
            (TARGET - timedelta(days=100), 5),
            (TARGET - timedelta(hours=999, minutes=30), 4),
            (TARGET + timedelta(hours=12), 1),
            (TARGET + timedelta(hours=26), 4),
        )
        for now, card_count in phase_slots:
            for slot in range(card_count):
                with self.subTest(now=now, slot=slot):
                    state = self.render(now, slot)
                    self.assertEqual(state.top_align, ALIGN_CENTER)
                    self.assertEqual(state.bottom_align, ALIGN_CENTER)

    def test_post_event_rotation(self):
        now = TARGET + timedelta(hours=26)
        expected = [
            ("$1,234", "IN 2026", True, False),
            ("RAISED", "FOR UCSF", False, False, False, True),
            ("$89,722", "ALL TIME", True, False),
            ("MORE AT", "STJ.WATCH", False, False, False, True),
        ]
        for slot, card in enumerate(expected):
            with self.subTest(slot=slot):
                self.assert_card(self.render(now, slot), *card)

    def test_unavailable_live_values_use_placeholder(self):
        countdown = self.render(
            TARGET - timedelta(hours=100),
            total_raised=None,
        )
        pre_all_time = self.render(
            TARGET - timedelta(days=100),
            slot=1,
            total_raised=None,
        )
        self.assertEqual(countdown.bottom_text, "--")
        self.assertEqual(pre_all_time.top_text, "--")

    def test_zero_is_a_real_live_total(self):
        state = self.render(TARGET - timedelta(hours=100), total_raised=0)
        self.assertEqual(state.bottom_text, "$0")

    def test_display_colors_follow_semantic_roles(self):
        top_money = DisplayState(
            phase=PHASE_PRE,
            top_text="$28,783",
            bottom_text="IN 2025",
            top_is_money=True,
        )
        bottom_money = DisplayState(
            phase=PHASE_COUNTDOWN,
            top_text="999:30:00",
            bottom_text="$1,234",
            bottom_is_money=True,
        )
        bottom_accent = DisplayState(
            phase=PHASE_PRE,
            top_text="MORE AT",
            bottom_text="STJ.WATCH",
            bottom_is_accent=True,
        )
        context_only = DisplayState(
            phase=PHASE_PRE,
            top_text="PLAIN",
            bottom_text="CONTEXT",
        )

        colors = {"context_color": 1, "money_color": 2, "accent_color": 3}
        self.assertEqual(display_colors(top_money, **colors), (2, 1))
        self.assertEqual(display_colors(bottom_money, **colors), (1, 2))
        self.assertEqual(display_colors(bottom_accent, **colors), (1, 3))
        self.assertEqual(display_colors(context_only, **colors), (1, 1))


if __name__ == "__main__":
    unittest.main()
