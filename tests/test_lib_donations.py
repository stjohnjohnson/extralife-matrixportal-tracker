"""Donation-feed behavior, with no hardware or live network dependency."""

import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from lib_donations import (
    DonationTracker,
    PollSchedule,
    _created_time,
    _date_text,
    _encode,
    api_server,
    fetch_json,
    normalize_donation,
)


def gift(identifier, second=1, **fields):
    record = {
        "donationID": identifier,
        "createdDateUTC": f"2026-10-12T12:00:{second:02d}.000+0000",
        "displayName": "Alex Johnson",
        "amount": 25.5,
        "donorID": "SAME-DONOR",
        "isRegFee": False,
        "message": None,
        "avatarImageURL": "https://example.org/avatar.png",
        "participantID": 123,
    }
    record.update(fields)
    return record


class DonationTrackerTests(unittest.TestCase):
    def test_legacy_extra_life_hosts_route_to_the_current_api(self):
        for server in ("https://www.extra-life.org", "https://extra-life.org/"):
            with self.subTest(server=server):
                self.assertEqual(api_server(server), "https://dd.extra-life.org")
                self.assertTrue(
                    DonationTracker()
                    .url(server, 565756)
                    .startswith(
                        "https://dd.extra-life.org/api/participants/565756/donations?"
                    )
                )
        self.assertEqual(
            api_server("https://dd.extra-life.org/"), "https://dd.extra-life.org"
        )
        self.assertEqual(
            api_server("https://custom.example.org/"), "https://custom.example.org"
        )

    def tracker(self, **kwargs):
        tracker = DonationTracker(**kwargs)
        tracker.accept_page([gift("BASE", 0)])
        return tracker

    def test_boot_establishes_baseline_without_replaying_history(self):
        tracker = DonationTracker()
        tracker.accept_page([gift("OLD", 0)])
        tracker.accept_page([gift("OLD", 0), gift("NEW", 1)])
        self.assertEqual(tracker.pop().donation_id, "NEW")
        self.assertIsNone(tracker.pop())

    def test_empty_initial_feed_still_recognizes_first_gift(self):
        tracker = DonationTracker()
        tracker.accept_page([])
        tracker.accept_page([gift("FIRST")])
        self.assertEqual(tracker.pop().donation_id, "FIRST")

    def test_several_gifts_from_same_donor_queue_individually(self):
        tracker = self.tracker()
        tracker.accept_page([gift("A", 1), gift("B", 2), gift("C", 3)])
        self.assertEqual([tracker.pop().donation_id for _ in range(3)], ["A", "B", "C"])

    def test_overlapping_pages_and_retries_do_not_replay(self):
        tracker = self.tracker(page_size=2)
        tracker.accept_page([gift("A", 1), gift("B", 2)])
        tracker.accept_page([gift("B", 2), gift("C", 3)])
        tracker.accept_page([])
        tracker.accept_page([gift("A", 1), gift("B", 2), gift("C", 3)])
        self.assertEqual([tracker.pop().donation_id for _ in range(3)], ["A", "B", "C"])
        self.assertIsNone(tracker.pop())

    def test_later_poll_can_find_smaller_id_at_the_same_timestamp(self):
        tracker = self.tracker()
        tracker.accept_page([gift("Z", 1)])
        tracker.pop()
        tracker.accept_page([gift("A", 1), gift("Z", 1)])
        self.assertEqual(tracker.pop().donation_id, "A")
        self.assertIsNone(tracker.pop())

    def test_queue_backpressure_preserves_unconsumed_gift(self):
        tracker = self.tracker(max_pending=2, page_size=3)
        tracker.accept_page([gift("A", 1), gift("B", 2), gift("C", 3)])
        query = parse_qs(urlsplit(tracker.url("https://example.org", 123)).query)
        self.assertIn("donationID > 'B'", query["where"][0])
        self.assertEqual(tracker.pop().donation_id, "A")
        tracker.accept_page([gift("C", 3)])
        self.assertEqual(tracker.pop().donation_id, "B")
        self.assertEqual(tracker.pop().donation_id, "C")

    def test_invalid_page_leaves_baseline_and_pending_intact(self):
        tracker = DonationTracker()
        before = tracker.url("https://example.org", 123)
        with self.assertRaises(ValueError):
            tracker.accept_page({"error": "unavailable"})
        self.assertEqual(tracker.url("https://example.org", 123), before)
        tracker.accept_page([gift("BASE", 0)])
        with self.assertRaises(ValueError):
            tracker.accept_page([gift("B", 2), gift("A", 1)])
        self.assertIsNone(tracker.pop())
        tracker.accept_page([gift("A", 1)])
        self.assertEqual(tracker.pop().donation_id, "A")

    def test_permanently_bad_amount_does_not_block_identifiable_gifts(self):
        tracker = self.tracker()
        page = [gift("A", 1), gift("B", 2, amount="bad"), gift("C", 3)]
        with patch("builtins.print") as diagnostic:
            for _ in range(3):
                tracker.accept_page(page)
            self.assertEqual(diagnostic.call_count, 1)
        self.assertEqual(
            [(d.donation_id, d.amount_text) for d in tracker.pending],
            [("A", "$25.50"), ("B", "THANKS!"), ("C", "$25.50")],
        )

    def test_invalid_keys_are_excluded_without_blocking_valid_neighbors(self):
        for field, value in (("donationID", "bad'ID"), ("createdDateUTC", "broken")):
            with self.subTest(field=field):
                tracker = self.tracker(page_size=3)
                page = [gift("A", 1), gift("BAD", 2, **{field: value}), gift("C", 3)]
                with patch("builtins.print"):
                    for _ in range(3):
                        tracker.accept_page(page)
                self.assertEqual([d.donation_id for d in tracker.pending], ["A", "C"])
                self.assertIn(
                    "donationID > 'C'",
                    parse_qs(urlsplit(tracker.url("https://example.org", 123)).query)[
                        "where"
                    ][0],
                )

    def test_invalid_baseline_or_wholly_invalid_page_retries_without_advancement(self):
        tracker = DonationTracker()
        before = tracker.url("https://example.org", 123)
        with self.assertRaises(ValueError):
            tracker.accept_page([gift("BAD", createdDateUTC="broken")])
        self.assertEqual(tracker.url("https://example.org", 123), before)
        tracker.accept_page([gift("BASE", 0)])
        tracker.accept_page([gift("A", 1)])
        before = tracker.url("https://example.org", 123)
        with patch("builtins.print"), self.assertRaises(ValueError):
            tracker.accept_page([{"error": "unavailable"}])
        self.assertEqual(tracker.url("https://example.org", 123), before)
        self.assertEqual(tracker.pop().donation_id, "A")

    def test_registration_fees_do_not_block_later_donations(self):
        tracker = self.tracker()
        tracker.accept_page([gift("FEE", 1, isRegFee=True), gift("GIFT", 2)])
        self.assertEqual(tracker.pop().donation_id, "GIFT")
        self.assertIsNone(tracker.pop())

    def test_url_uses_small_pages_and_stable_ascending_keyset(self):
        tracker = self.tracker(page_size=2)
        tracker.accept_page([gift("A", 1), gift("B", 1)])
        query = parse_qs(urlsplit(tracker.url("https://example.org/", 123)).query)
        self.assertEqual(query["limit"], ["2"])
        self.assertEqual(query["version"], ["1.3"])
        self.assertEqual(query["orderBy"], ["createdDateUTC ASC,donationID ASC"])
        self.assertIn(
            "createdDateUTC = '2026-10-12T12:00:01.000+0000'", query["where"][0]
        )
        self.assertIn("donationID > 'B'", query["where"][0])

    def test_bounded_deduplication_does_not_replay_retired_records(self):
        tracker = self.tracker(max_seen=2)
        tracker.accept_page([gift("A", 1), gift("B", 2), gift("C", 3)])
        for _ in range(3):
            tracker.pop()
        tracker.accept_page([gift("A", 1), gift("B", 2), gift("C", 3), gift("D", 4)])
        self.assertEqual(tracker.pop().donation_id, "D")
        self.assertIsNone(tracker.pop())


class DonationNormalizationTests(unittest.TestCase):
    def test_query_encoding_works_without_circuitpython_isalnum(self):
        class DeviceString(str):
            def isalnum(self):
                raise AttributeError("CircuitPython has no str.isalnum")

            def __iter__(self):
                return (DeviceString(character) for character in super().__iter__())

        with patch.dict(_encode.__globals__, {"str": DeviceString}):
            self.assertEqual(
                _encode("date >= 'X+0000'"), "date%20%3E%3D%20%27X%2B0000%27"
            )

    def test_cursor_dates_round_trip_without_a_device_gmtime_function(self):
        dates = (
            "1970-01-01T00:00:00.000+0000",
            "2000-02-29T23:59:59.123456+0000",
            "2026-10-12T12:00:01.123+0000",
            "2028-03-01T00:00:00.000+0000",
            "2099-12-31T23:59:59.000001+0000",
        )
        with patch.dict(_date_text.__globals__, {"time": object()}):
            for date in dates:
                with self.subTest(date=date):
                    self.assertEqual(_date_text(_created_time(date)), date)

    def test_preserves_public_amount_cents_and_grouping(self):
        for amount, expected in ((25, "$25"), (25.5, "$25.50"), (1234.01, "$1,234.01")):
            with self.subTest(amount=amount):
                self.assertEqual(
                    normalize_donation(gift("A", amount=amount)).amount_text, expected
                )

    def test_private_fields_use_fallbacks_without_looking_at_total(self):
        record = gift("A")
        del record["displayName"]
        del record["amount"]
        donation = normalize_donation(record)
        self.assertEqual((donation.amount_text, donation.name), ("THANKS!", "ANON"))

    def test_names_use_supported_ascii_and_visible_truncation(self):
        self.assertEqual(
            normalize_donation(gift("A", displayName="  Alex\nZoë 🎉 ")).name,
            "ALEX ZO? ?",
        )
        self.assertEqual(normalize_donation(gift("A", displayName="  ")).name, "ANON")
        name = normalize_donation(gift("A", displayName="X" * 1000)).name
        self.assertEqual(name, "X" * 45 + "...")

    def test_malformed_identity_and_date_fail(self):
        for field, value in (
            ("donationID", "bad'ID"),
            ("createdDateUTC", "2026-02-30T12:00:00Z"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    normalize_donation(gift("A", **{field: value}))

    def test_invalid_amounts_use_thanks_without_inventing_a_value(self):
        for value in (float("nan"), float("inf"), -1, "oops", True, 1e10):
            with self.subTest(value=value):
                self.assertEqual(
                    normalize_donation(gift("A", amount=value)).amount_text, "THANKS!"
                )


class PollScheduleTests(unittest.TestCase):
    def test_faster_frames_do_not_increase_request_rate(self):
        schedule = PollSchedule(30)
        self.assertEqual(schedule.ready(0), "sync")
        schedule.record("sync", 0, True)
        self.assertEqual(schedule.ready(0), "total")
        schedule.record("total", 0, True)
        self.assertIsNone(schedule.ready(14.99))
        self.assertEqual(schedule.ready(15), "donations")
        schedule.record("donations", 15, True)
        self.assertEqual(schedule.ready(30), "total")

    def test_motion_and_full_queue_defer_work_without_starving_total(self):
        schedule = PollSchedule(30)
        self.assertIsNone(schedule.ready(0, busy=True))
        schedule.record("sync", 0, True)
        schedule.record("total", 0, True)
        self.assertIsNone(schedule.ready(15, feed_has_room=False))
        self.assertEqual(schedule.ready(30, feed_has_room=False), "total")

    def test_failures_back_off_and_success_resets_retry_delay(self):
        schedule = PollSchedule(30)
        schedule.record("sync", 0, True)
        schedule.record("total", 0, True)
        schedule.record("donations", 15, False)
        schedule.record("total", 30, True)
        self.assertEqual(schedule.ready(45), "donations")
        schedule.record("donations", 45, False)
        schedule.record("total", 60, True)
        self.assertIsNone(schedule.ready(75))
        schedule.record("total", 90, True)
        self.assertEqual(schedule.ready(105), "donations")


class Response:
    def __init__(self, status, data=None, error=None):
        self.status_code, self.data, self.error = status, data, error
        self.closed = False

    def json(self):
        if self.error:
            raise self.error
        return self.data

    def close(self):
        self.closed = True


class Network:
    def __init__(self, response):
        self.response = response

    def fetch(self, url):
        return self.response


class FetchJsonTests(unittest.TestCase):
    def test_responses_close_on_success_http_failure_and_invalid_json(self):
        for response in (
            Response(200, [gift("A")]),
            Response(429),
            Response(200, error=ValueError("bad JSON")),
        ):
            with self.subTest(status=response.status_code, error=response.error):
                if response.status_code == 200 and not response.error:
                    self.assertEqual(fetch_json(Network(response), "url"), [gift("A")])
                else:
                    with self.assertRaises((ValueError, RuntimeError)):
                        fetch_json(Network(response), "url")
                self.assertTrue(response.closed)

    def test_empty_page_status_is_not_parsed_as_json(self):
        response = Response(204, error=ValueError("no body"))
        self.assertEqual(fetch_json(Network(response), "url", empty_list=True), [])
        self.assertTrue(response.closed)
