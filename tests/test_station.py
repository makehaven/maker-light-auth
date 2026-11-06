"""Tests for pairing, the saved config, and the box-then-website rules.

Run from the repository root: python -m unittest discover -s tests
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import station  # noqa: E402

GRANTED = [{"access": "true", "first_name": "Ada", "last_name": "Lovelace"}]


class FakeServer:
    """A local HTTP server that records requests and replays a set answer."""

    def __init__(self, status=200, body=None):
        self.status = status
        self.body = body
        self.requests = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _answer(self):
                length = int(self.headers.get("Content-Length") or 0)
                sent = self.rfile.read(length).decode() if length else ""
                fake.requests.append({"path": self.path, "headers": dict(self.headers), "body": sent})
                raw = fake.body if isinstance(fake.body, bytes) else json.dumps(fake.body).encode()
                self.send_response(fake.status)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            do_GET = _answer
            do_POST = _answer

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


def dead_url():
    """An address nothing is listening on."""
    fake = FakeServer()
    url = fake.url
    fake.stop()
    return url


class StationTestCase(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.mkdtemp()
        os.environ["MAKERAUTH_STATE_DIR"] = self.state
        self.addCleanup(shutil.rmtree, self.state, True)
        self.addCleanup(os.environ.pop, "MAKERAUTH_STATE_DIR", None)
        self.addCleanup(setattr, station, "WEBSITE_URL", station.WEBSITE_URL)

    def serve(self, status=200, body=None):
        fake = FakeServer(status, body if body is not None else {})
        self.addCleanup(fake.stop)
        return fake

    def config(self, box=None):
        return {
            "station": {"source_id": "laser_2_computer", "permission_id": "laser_cutter"},
            "access": {"local_url": box.url if box else ""},
        }


class CheckAccessTests(StationTestCase):
    def test_box_answer_is_used_and_website_not_asked(self):
        box = self.serve(200, GRANTED)
        website = self.serve(200, GRANTED)
        station.WEBSITE_URL = website.url
        response = station.check_access("ada@example.com", True, self.config(box), "secret-key")
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(box.requests))
        self.assertEqual(0, len(website.requests))

    def test_key_never_goes_to_the_box(self):
        box = self.serve(500, b"broken")
        website = self.serve(200, GRANTED)
        station.WEBSITE_URL = website.url
        station.check_access("01020304", False, self.config(box), "secret-key")
        self.assertNotIn("X-API-Key", box.requests[0]["headers"])
        self.assertNotIn("secret-key", json.dumps(box.requests[0]))
        self.assertEqual("secret-key", website.requests[0]["headers"]["X-API-Key"])

    def test_verdicts_from_the_box_are_not_asked_twice(self):
        for status in (403, 404):
            box = self.serve(status, {"error": "no"})
            website = self.serve(200, GRANTED)
            station.WEBSITE_URL = website.url
            response = station.check_access("01020304", False, self.config(box), "k")
            self.assertEqual(status, response.status_code)
            self.assertEqual(0, len(website.requests), f"{status} must not reach the website")

    def test_box_that_cannot_answer_falls_through_to_website(self):
        cases = [(500, b"oops"), (401, {"error": "x"}), (400, {"error": "Invalid permission ID."}), (200, b"<html>nope</html>"), (200, {"not": "a list"})]
        for status, body in cases:
            box = self.serve(status, body)
            website = self.serve(200, GRANTED)
            station.WEBSITE_URL = website.url
            response = station.check_access("01020304", False, self.config(box), "k")
            self.assertEqual(1, len(website.requests), f"box {status} {body!r}")
            self.assertEqual(200, response.status_code)

    def test_box_down_falls_through_to_website(self):
        website = self.serve(200, GRANTED)
        station.WEBSITE_URL = website.url
        config = self.config()
        config["access"]["local_url"] = dead_url()
        self.assertEqual(200, station.check_access("01020304", False, config, "k").status_code)

    def test_nothing_reachable_returns_none(self):
        station.WEBSITE_URL = dead_url()
        config = self.config()
        config["access"]["local_url"] = dead_url()
        self.assertIsNone(station.check_access("01020304", False, config, "k"))

    def test_without_a_box_only_the_website_is_asked(self):
        website = self.serve(200, GRANTED)
        station.WEBSITE_URL = website.url
        station.check_access("01020304", False, self.config(), "k")
        self.assertEqual(1, len(website.requests))

    def test_request_names_the_station_and_escapes_the_identifier(self):
        box = self.serve(200, GRANTED)
        station.WEBSITE_URL = dead_url()
        station.check_access("a/b@example.com", True, self.config(box), "k")
        path = box.requests[0]["path"]
        self.assertIn("/api/v0/email/a%2Fb%40example.com/permission/laser_cutter", path)
        self.assertIn("source=laser_2_computer", path)
        self.assertIn("method=MakerAuth", path)


class PairingAndConfigTests(StationTestCase):
    def test_pairing_saves_key_and_config(self):
        website = self.serve(200, {"key": "mhst_abc", "config": {"station": {"name": "Laser 2"}}})
        station.WEBSITE_URL = website.url
        outcome, config = station.pair("ABCD-EFGH")
        self.assertEqual(station.OK, outcome)
        self.assertEqual("Laser 2", config["station"]["name"])
        self.assertEqual("mhst_abc", station.load_key())
        self.assertEqual("Laser 2", station.load_saved_config()["station"]["name"])
        self.assertEqual({"code": "ABCD-EFGH"}, json.loads(website.requests[0]["body"]))

    def test_wrong_code_saves_nothing(self):
        station.WEBSITE_URL = self.serve(403, {"error": "That pairing code is wrong"}).url
        self.assertEqual(station.BAD_CODE, station.pair("NOPE-NOPE")[0])
        self.assertEqual("", station.load_key())

    def test_pairing_while_offline_is_not_a_bad_code(self):
        station.WEBSITE_URL = dead_url()
        self.assertEqual(station.OFFLINE, station.pair("ABCD-EFGH")[0])

    def test_config_sends_key_and_version_and_is_saved(self):
        website = self.serve(200, {"station": {"name": "Laser 2"}})
        station.WEBSITE_URL = website.url
        outcome, _config = station.fetch_config("mhst_abc")
        self.assertEqual(station.OK, outcome)
        self.assertEqual("mhst_abc", website.requests[0]["headers"]["X-API-Key"])
        self.assertEqual(station.VERSION, website.requests[0]["headers"]["X-Station-Version"])
        self.assertEqual("Laser 2", station.load_saved_config()["station"]["name"])

    def test_only_a_401_means_revoked(self):
        station.WEBSITE_URL = self.serve(401, {"error": "Station not recognized."}).url
        self.assertEqual(station.REVOKED, station.fetch_config("k")[0])

    def test_outage_keeps_the_saved_config(self):
        station.save_config({"station": {"name": "Saved"}})
        for status, body in ((500, b"oops"), (503, b"down"), (200, b"<html>maintenance</html>"), (200, {"no": "station"})):
            station.WEBSITE_URL = self.serve(status, body).url
            self.assertEqual(station.OFFLINE, station.fetch_config("k")[0], f"{status} {body!r}")
        station.WEBSITE_URL = dead_url()
        self.assertEqual(station.OFFLINE, station.fetch_config("k")[0])
        self.assertEqual("Saved", station.load_saved_config()["station"]["name"])

    def test_damaged_saved_config_reads_as_none(self):
        with open(station.state_path("station-config.json"), "w", encoding="utf-8") as handle:
            handle.write('{"station": ')
        self.assertIsNone(station.load_saved_config())

    @unittest.skipIf(sys.platform == "win32", "POSIX file modes")
    def test_key_file_is_private(self):
        station.save_key("mhst_abc")
        self.assertEqual(0o600, os.stat(station.state_path("station.key")).st_mode & 0o777)

    def test_forget_key(self):
        station.save_key("mhst_abc")
        station.forget_key()
        self.assertEqual("", station.load_key())
        station.forget_key()


class ReportTests(StationTestCase):
    REPORT = {"issue_type": "software", "description": "It will not open."}

    def test_report_is_sent_with_the_key(self):
        website = self.serve(200, {"ok": True})
        station.WEBSITE_URL = website.url
        station.save_key("mhst_abc")
        self.assertEqual(station.REPORT_SENT, station.submit_report(self.REPORT)[0])
        self.assertEqual("mhst_abc", website.requests[0]["headers"]["X-API-Key"])
        self.assertEqual(self.REPORT, json.loads(website.requests[0]["body"]))
        self.assertEqual([], station._load_pending_reports())

    def test_outage_keeps_the_report_and_sends_it_later_in_order(self):
        station.WEBSITE_URL = dead_url()
        second = dict(self.REPORT, description="Second")
        self.assertEqual(station.REPORT_SAVED, station.submit_report(self.REPORT)[0])
        self.assertEqual(station.REPORT_SAVED, station.submit_report(second)[0])
        self.assertEqual(2, len(station._load_pending_reports()))

        website = self.serve(200, {"ok": True})
        station.WEBSITE_URL = website.url
        station.send_pending_reports()
        self.assertEqual([self.REPORT, second], [json.loads(r["body"]) for r in website.requests])
        self.assertEqual([], station._load_pending_reports())

    def test_server_errors_keep_the_report(self):
        for status in (401, 429, 500, 503):
            station.WEBSITE_URL = self.serve(status, {"error": "no"}).url
            self.assertEqual(station.REPORT_SAVED, station.submit_report(self.REPORT)[0], status)
        self.assertEqual(4, len(station._load_pending_reports()))

    def test_a_refused_report_says_why_and_is_not_kept(self):
        station.WEBSITE_URL = self.serve(400, {"error": "Please describe the problem."}).url
        self.assertEqual((station.REPORT_REJECTED, "Please describe the problem."), station.submit_report(self.REPORT))
        self.assertEqual([], station._load_pending_reports())

    def test_a_stuck_report_does_not_lose_the_rest(self):
        station.WEBSITE_URL = dead_url()
        station.submit_report(self.REPORT)
        station.submit_report(dict(self.REPORT, description="Second"))
        station.WEBSITE_URL = self.serve(500, b"oops").url
        station.send_pending_reports()
        self.assertEqual(2, len(station._load_pending_reports()))


class DisplayTests(StationTestCase):
    def test_ended_reservations_drop_off_a_saved_copy(self):
        now = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
        config = {"reservations": [
            {"id": 1, "end": (now - timedelta(minutes=1)).isoformat()},
            {"id": 2, "end": (now + timedelta(minutes=1)).isoformat()},
            {"id": 3},
        ]}
        self.assertEqual([2, 3], [r["id"] for r in station.upcoming_reservations(config, now)])

    def test_in_progress_comes_from_this_clock_not_the_saved_copy(self):
        now = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
        config = {"reservations": [{
            "id": 1,
            "start": (now - timedelta(minutes=5)).isoformat(),
            "end": (now + timedelta(minutes=5)).isoformat(),
            "in_progress": False,
        }, {
            "id": 2,
            "start": (now + timedelta(minutes=5)).isoformat(),
            "end": (now + timedelta(minutes=9)).isoformat(),
            "in_progress": True,
        }]}
        self.assertEqual([True, False], [r["in_progress"] for r in station.upcoming_reservations(config, now)])
        self.assertFalse(config["reservations"][0]["in_progress"], "The saved copy isn't changed.")

    def test_signature_ignores_only_what_is_not_drawn(self):
        now = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
        end = (now + timedelta(hours=1)).isoformat()
        config = {"server_time": "a", "display": {"end_message": "x"}, "reservations": [{"id": 1, "start": now.isoformat(), "end": end}]}
        same = dict(config, server_time="b")
        self.assertEqual(station.display_signature(config, True, now), station.display_signature(same, True, now))
        self.assertNotEqual(station.display_signature(config, True, now), station.display_signature(config, False, now))
        changed = dict(config, display={"end_message": "y"})
        self.assertNotEqual(station.display_signature(config, True, now), station.display_signature(changed, True, now))
        later = now + timedelta(hours=2)
        self.assertNotEqual(station.display_signature(config, True, now), station.display_signature(config, True, later),
                            "A reservation ending changes the screen with no network call.")

    def test_reservation_parts(self):
        parts = station.reservation_parts({
            "equipment": "Laser 2",
            "start": "2026-11-06T14:00:00-05:00",
            "end": "2026-11-06T15:30:00-05:00",
            "member": "Jane D.",
            "purpose": "Signs",
        })
        self.assertEqual(("Laser 2", "Fri Nov 6, 2:00 PM to 3:30 PM", "Jane D. · Signs"), parts)

    def test_reservation_parts_survive_missing_fields(self):
        self.assertEqual(("Reservation", "Time unknown", ""), station.reservation_parts({}))

    def test_noon_and_midnight(self):
        _title, when, _who = station.reservation_parts({"start": "2026-11-06T00:05:00", "end": "2026-11-06T12:00:00"})
        self.assertIn("12:05 AM to 12:00 PM", when)

    def test_status_notices(self):
        config = {"equipment": [
            {"title": "Fine", "status": {"label": "Operational", "level": "ok"}},
            {"title": "Slow", "status": {"label": "Degraded", "level": "notice", "note": "Weak tube."}},
            {"title": "Flagged", "status": {"label": "Reported Concern", "level": "notice", "note": "Member Report (Ada): x"}},
            {"title": "Down", "status": {"label": "Out of Service", "level": "down", "expected_back": "2026-11-20"}},
            {"title": "Old site, no status"},
        ]}
        self.assertEqual([
            ("bad", "Down: Out of Service. Expected back Nov 20."),
            ("warn", "Slow: Degraded. Weak tube."),
            ("warn", "Flagged: a problem was reported. Staff are checking it."),
        ], station.status_notices(config))

    def test_a_long_status_note_is_shortened(self):
        config = {"equipment": [{"title": "T", "status": {"label": "Degraded", "level": "notice", "note": "x" * 900}}]}
        self.assertLess(len(station.status_notices(config)[0][1]), 300)

    def test_issue_choices_follow_the_station(self):
        tool = [key for key, _label in station.issue_choices({"equipment": [{"id": 1}]})]
        self.assertIn("broken_nonfuctional", tool)
        self.assertIn("software", tool)
        desk = [key for key, _label in station.issue_choices({"equipment": []})]
        self.assertEqual(["software", "computer", "other"], desk)
        self.assertTrue(station.is_tool_issue("parts_missing"))
        self.assertFalse(station.is_tool_issue("software"))

    def test_denial_reasons(self):
        website = self.serve(403, {"error": "Your membership is paused."})
        response = station.requests.get(website.url)
        self.assertEqual("Denied: Your membership is paused.", station.denial_reason(response))

    def test_log_writes_a_header_once(self):
        station.log_event("start", {"first_name": "Ada", "last_name": "L"})
        station.log_event("end", {"first_name": "Ada", "last_name": "L"}, duration="0:10:00")
        with open(station.state_path("SessionLog.csv"), encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        self.assertEqual(3, len(lines))
        self.assertTrue(lines[0].startswith("Timestamp,"))


if __name__ == "__main__":
    unittest.main()
