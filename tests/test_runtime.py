"""Execute the real device script against BDF-backed display and HTTP doubles."""

import re
import sys
import types
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from tools.render_display_previews import ROOT, layout_text, load_bdf


class EndSimulation(BaseException):
    pass


class Bitmap(list):
    def __init__(self, width, height, colors):
        super().__init__([0] * (width * height))
        self.width, self.height = width, height

    def fill(self, value):
        self[:] = [value] * len(self)


class Group(list):
    hidden = False

    def append(self, item):
        item.parent = self
        super().append(item)


class Palette(list):
    def __init__(self, count):
        super().__init__([0] * count)

    def make_transparent(self, index):
        pass


class TileGrid:
    def __init__(self, bitmap, pixel_shader):
        self.bitmap, self.pixel_shader = bitmap, pixel_shader


class Label:
    def __init__(self, font, background_tight=True):
        self.font, self.text, self.color, self.x, self.y = font, "", 0, 0, 0

    @property
    def bounding_box(self):
        return layout_text(self.font, self.text).bounding_box


class Response:
    def __init__(self, data, status=200):
        self.data, self.status_code, self.closed = data, status, False

    def json(self):
        return self.data

    def close(self):
        self.closed = True


def module(name, **fields):
    result = types.ModuleType(name)
    result.__dict__.update(fields)
    return result


class Simulation:
    def __init__(
        self, base=datetime(2026, 10, 12, 12), fail_feed=False, total_responses=None
    ):
        self.now, self.base, self.fail_feed = 0.0, base, fail_feed
        self.labels, self.requests, self.responses, self.celebrated = [], [], [], []
        self.animation_frames = 0
        self.display = types.SimpleNamespace(width=64, height=32, root_group=None)
        self.font = load_bdf(ROOT / "Micro5-Regular-21.bdf")
        self.total_responses = list(total_responses or [])
        self.goal_observations = []
        self.namespace = None

    def donation(self, identifier, second, name):
        created = (self.base + timedelta(seconds=second)).isoformat(
            timespec="milliseconds"
        )
        return {
            "donationID": identifier,
            "createdDateUTC": created + "+0000",
            "displayName": name,
            "amount": 25.5,
            "isRegFee": False,
        }

    def fetch(self, url):
        busy = bool(self.labels and self.labels[0].parent.hidden)
        self.requests.append((self.now, url, busy))
        self.now += 0.4  # Real synchronous requests delay the device loop.
        if "/donations?" not in url:
            response = (
                self.total_responses.pop(0)
                if self.total_responses
                else Response(
                    {
                        "sumDonations": 100 + (51 if self.now >= 21 else 0),
                        "fundraisingGoal": 1000,
                    }
                )
            )
            if isinstance(response, Exception):
                raise response
        else:
            feed_calls = sum("/donations?" in request[1] for request in self.requests)
            if self.fail_feed and feed_calls == 2:
                response = Response({"error": "rate limited"}, 429)
            else:
                records = [self.donation("OLD", -1, "Old Gift")]
                if self.now >= 21:
                    records += [
                        self.donation("NEW-A", 20, "Alex Johnson"),
                        self.donation("NEW-B", 21, "Sam"),
                    ]
                query = parse_qs(urlsplit(url).query)
                if "DESC" in query.get("orderBy", [""])[0]:
                    records.reverse()
                where = query.get("where", [""])[0]
                lower = re.search(r"createdDateUTC >= '([^']+)'", where)
                cursor = re.search(
                    r"createdDateUTC = '([^']+)' AND donationID > '([^']+)'", where
                )
                if lower:
                    records = [r for r in records if r["createdDateUTC"] >= lower[1]]
                if cursor:
                    records = [
                        r
                        for r in records
                        if (r["createdDateUTC"], r["donationID"])
                        > (cursor[1], cursor[2])
                    ]
                response = Response(records[: int(query.get("limit", ["10"])[0])])
        self.responses.append(response)
        return response

    def sleep(self, seconds):
        if self.namespace and "goal_bar" in self.namespace:
            self.goal_observations.append(
                (
                    bool(self.namespace["active_celebration"]),
                    self.namespace["goal_bar"].hidden,
                )
            )
        if len(self.labels) >= 4 and not self.labels[2].parent.hidden:
            name = self.labels[3].text
            if not self.celebrated or self.celebrated[-1][0] != name:
                self.celebrated.append(
                    (
                        name,
                        self.labels[2].text,
                        self.labels[2].color,
                        self.labels[3].color,
                    )
                )
        if self.labels and self.labels[0].parent.hidden:
            self.animation_frames += 1
        self.now += seconds
        if self.now >= 115:
            raise EndSimulation

    def run(self):
        simulation = self

        class DeviceDatetime(datetime):
            @classmethod
            def now(cls):
                return simulation.base + timedelta(seconds=simulation.now)

        def label(*args, **kwargs):
            item = Label(*args, **kwargs)
            self.labels.append(item)
            return item

        class MatrixPortal:
            def __init__(self, **kwargs):
                self.display = simulation.display
                self.network = simulation

            def get_local_time(self, zone):
                simulation.now += 0.1

        modules = {
            "board": module("board", NEOPIXEL=object()),
            "displayio": module(
                "displayio",
                Group=Group,
                Bitmap=Bitmap,
                Palette=Palette,
                TileGrid=TileGrid,
            ),
            "adafruit_bitmap_font": module(
                "adafruit_bitmap_font",
                bitmap_font=types.SimpleNamespace(load_font=lambda path: self.font),
            ),
            "adafruit_datetime": module("adafruit_datetime", datetime=DeviceDatetime),
            "adafruit_display_text": module("adafruit_display_text"),
            "adafruit_display_text.label": module(
                "adafruit_display_text.label", Label=label
            ),
            "adafruit_matrixportal": module("adafruit_matrixportal"),
            "adafruit_matrixportal.matrixportal": module(
                "adafruit_matrixportal.matrixportal", MatrixPortal=MatrixPortal
            ),
            "secrets": module(
                "secrets",
                secrets={
                    "extralife_id": "123",
                    "target_date": "2026-11-07T16:30:00",
                    "extralife_server": "https://www.extra-life.org",
                },
            ),
        }
        namespace = {"__name__": "__main__"}
        self.namespace = namespace
        with patch.dict(sys.modules, modules), patch(
            "time.monotonic", lambda: self.now
        ), patch("time.sleep", self.sleep), patch("builtins.print"):
            try:
                exec(
                    compile(
                        (ROOT / "code.py").read_text(), str(ROOT / "code.py"), "exec"
                    ),
                    namespace,
                )
            except EndSimulation:
                pass
        return namespace


class DeviceLoopTests(unittest.TestCase):
    def test_goal_bar_stays_hidden_when_initial_total_requests_fail(self):
        simulation = Simulation(total_responses=[Response({}, 503) for _ in range(8)])
        namespace = simulation.run()
        self.assertIsNone(namespace["donation_cache"][3])
        self.assertIsNone(namespace["donation_cache"][4])
        self.assertTrue(namespace["goal_bar"].hidden)
        self.assertTrue(all(hidden for _, hidden in simulation.goal_observations))

    def test_goal_bar_fills_both_bottom_rows_and_hides_after_zero_goal(self):
        simulation = Simulation(base=datetime(2026, 11, 7, 17))
        namespace = simulation.run()
        simulation.total_responses.append(
            Response({"sumDonations": 730, "fundraisingGoal": 1000})
        )
        namespace["money_raised"](False)
        with patch("time.monotonic", lambda: simulation.now):
            namespace["update_display"]()
        self.assertFalse(namespace["goal_bar"].hidden)
        self.assertEqual(namespace["goal_bar"].y, 30)
        self.assertEqual(namespace["goal_bitmap"], ([1] * 47 + [0] * 17) * 2)
        self.assertEqual(namespace["goal_bar"].pixel_shader, [0x17280C, 0x85FF00])
        simulation.total_responses.append(
            Response({"sumDonations": 730, "fundraisingGoal": 0})
        )
        namespace["money_raised"](False)
        with patch("time.monotonic", lambda: simulation.now):
            namespace["update_display"]()
        self.assertTrue(namespace["goal_bar"].hidden)

    def test_invalid_total_refresh_keeps_total_and_goal_together(self):
        simulation = Simulation(base=datetime(2026, 11, 7, 17))
        namespace = simulation.run()
        simulation.total_responses.append(
            Response({"sumDonations": 730, "fundraisingGoal": 1000})
        )
        self.assertEqual(
            namespace["money_raised"](False), ("$730", "$1,000", 73.0, 730, 1000)
        )
        expected = ["$730", "$1,000", 73.0, 730, 1000]
        for response in (
            OSError("offline"),
            Response({}, 503),
            Response({"sumDonations": 800}),
            Response({"sumDonations": 800, "fundraisingGoal": "bad"}),
            Response({"sumDonations": True, "fundraisingGoal": 2000}),
            Response({"sumDonations": 800, "fundraisingGoal": True}),
            Response({"sumDonations": float("nan"), "fundraisingGoal": 2000}),
        ):
            with self.subTest(response=response):
                simulation.total_responses.append(response)
                with self.assertRaises((OSError, RuntimeError, KeyError, ValueError)):
                    namespace["money_raised"](False)
                self.assertEqual(namespace["donation_cache"], expected)
                with patch("time.monotonic", lambda: simulation.now):
                    namespace["update_display"]()
                self.assertFalse(namespace["goal_bar"].hidden)
                self.assertEqual(namespace["goal_bitmap"], ([1] * 47 + [0] * 17) * 2)

    def test_goal_layer_follows_all_annual_rotation_cards(self):
        for base, hidden in (
            (datetime(2026, 1, 1), (True, True, True, True, True)),
            (datetime(2026, 10, 12), (False, True, False, True)),
            (datetime(2026, 11, 7, 17), (False,)),
            (datetime(2026, 12, 1), (False, True, True, True)),
        ):
            simulation = Simulation(base=base)
            namespace = simulation.run()
            for slot in range(len(hidden) * 2):
                with self.subTest(base=base, slot=slot):
                    clock = namespace["rotation_clock"]
                    clock.elapsed = slot * 15
                    clock.updated_at = simulation.now
                    clock.paused = False
                    with patch("time.monotonic", lambda: simulation.now):
                        namespace["update_display"]()
                    self.assertEqual(
                        namespace["goal_bar"].hidden, hidden[slot % len(hidden)]
                    )

    def test_goal_bar_hides_for_entire_celebration_and_returns_afterward(self):
        simulation = Simulation(base=datetime(2026, 11, 7, 17))
        namespace = simulation.run()
        busy = [hidden for active, hidden in simulation.goal_observations if active]
        self.assertTrue(busy)
        self.assertTrue(all(busy))
        self.assertFalse(namespace["goal_bar"].hidden)
        self.assertTrue(
            any(
                not hidden
                for active, hidden in simulation.goal_observations
                if not active
            )
        )
        self.assertEqual(namespace["old_snapshot"][-128:], [0] * 128)
        self.assertEqual(namespace["new_snapshot"][-128:], [0] * 128)

    def test_frame_budget_includes_rendering_time(self):
        from lib_celebration import starburst_frame

        simulation = Simulation()
        frame_times = []

        def slower_starburst(*args):
            frame_times.append(simulation.now)
            starburst_frame(*args)
            simulation.now += 0.04

        with patch("lib_celebration.starburst_frame", slower_starburst):
            simulation.run()
        first_entrance = [t for t in frame_times if t < frame_times[0] + 0.9]
        self.assertGreaterEqual(len(first_entrance), 15)

    def test_snapshot_failure_restores_display_and_retries_the_same_donor(self):
        simulation = Simulation(base=datetime(2026, 11, 7, 17))
        original_glyph = simulation.font.get_glyph
        failures = []

        def flaky_glyph(code_point):
            if (
                len(simulation.labels) == 4
                and simulation.labels[2].text
                and not failures
            ):
                failures.append(simulation.now)
                raise RuntimeError("Synthetic snapshot failure")
            return original_glyph(code_point)

        simulation.font.get_glyph = flaky_glyph
        namespace = simulation.run()
        self.assertEqual(len(failures), 1)
        self.assertEqual(
            [gift[0] for gift in simulation.celebrated], ["ALEX JOHNSON", "SAM"]
        )
        self.assertFalse(namespace["normal_group"].hidden)
        self.assertTrue(namespace["donation_group"].hidden)
        self.assertEqual(namespace["tracker"].pending, [])
        self.assertFalse(any(namespace["bitmap"]))
        self.assertFalse(any(namespace["sparkles"]))
        self.assertFalse(namespace["goal_bar"].hidden)
        self.assertTrue(
            all(hidden for active, hidden in simulation.goal_observations if active)
        )

    def test_slow_label_preparation_does_not_consume_the_entrance(self):
        simulation = Simulation()
        namespace = simulation.run()
        from lib_donations import normalize_donation

        namespace["tracker"].pending.append(
            normalize_donation(simulation.donation("NEXT", 120, "SAM"))
        )
        simulation.now = 0
        original_paint = namespace["paint_text"]

        def slow_paint(*args):
            original_paint(*args)
            simulation.now += 1

        namespace["paint_text"] = slow_paint
        with patch("time.monotonic", lambda: simulation.now):
            namespace["start_celebration"](simulation.now)
            self.assertEqual(namespace["celebration_started_at"], simulation.now)
            namespace["update_celebration"](simulation.now)
            self.assertEqual(namespace["bitmap"], namespace["old_snapshot"])

    def test_individual_blue_names_starburst_and_response_release(self):
        simulation = Simulation()
        namespace = simulation.run()
        self.assertEqual(
            simulation.celebrated,
            [
                ("ALEX JOHNSON", "$25.50", 0x85FF00, 0x1AC1DD),
                ("SAM", "$25.50", 0x85FF00, 0x1AC1DD),
            ],
        )
        self.assertGreater(simulation.animation_frames, 60)
        self.assertTrue(all(response.closed for response in simulation.responses))
        self.assertTrue(
            all(
                url.startswith("https://dd.extra-life.org/api/")
                for _, url, _ in simulation.requests
            )
        )
        self.assertTrue(all(not busy for _, _, busy in simulation.requests))
        self.assertTrue(
            all(
                b[0] - a[0] >= 15
                for a, b in zip(simulation.requests, simulation.requests[1:])
            )
        )
        self.assertFalse(namespace["normal_group"].hidden)
        self.assertEqual(set(namespace["bitmap"]), {0})

    def test_rate_limited_feed_recovers_and_keeps_total_live(self):
        simulation = Simulation(fail_feed=True)
        namespace = simulation.run()
        self.assertEqual(
            [entry[0] for entry in simulation.celebrated], ["ALEX JOHNSON", "SAM"]
        )
        self.assertEqual(namespace["donation_cache"][3], 151)

    def test_celebrations_are_eligible_before_during_and_after_event(self):
        for base in (
            datetime(2026, 1, 1),
            datetime(2026, 11, 7, 17),
            datetime(2026, 12, 1),
        ):
            with self.subTest(base=base):
                simulation = Simulation(base=base)
                simulation.run()
                self.assertEqual(
                    [entry[0] for entry in simulation.celebrated],
                    ["ALEX JOHNSON", "SAM"],
                )
