"""Tests the part of station setup that runs on the computer, after Python is there."""
import contextlib
import importlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import setup_station  # noqa: E402
import station  # noqa: E402


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state, True)
        patcher = mock.patch.dict(os.environ, {"MAKERAUTH_STATE_DIR": self.state})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("MAKERAUTH_WEBSITE_URL", None)
        os.environ.pop(setup_station.CODE_VARIABLE, None)
        self.addCleanup(importlib.reload, station)

    def pair(self, code="ABCD-EFGH", outcome=station.OK):
        if code:
            os.environ[setup_station.CODE_VARIABLE] = code
        config = {"station": {"name": "Laser 2"}} if outcome == station.OK else None
        output = io.StringIO()
        with mock.patch.object(station, "pair", return_value=(outcome, config)) as pair, \
                contextlib.redirect_stdout(output):
            result = setup_station.pair_this_computer()
        return result, output.getvalue(), pair

    def test_a_good_code_pairs(self):
        result, output, pair = self.pair()
        self.assertEqual(0, result)
        self.assertIn("Laser 2", output)
        pair.assert_called_once_with("ABCD-EFGH")

    def test_a_used_code_leaves_a_paired_computer_alone(self):
        station.save_key("mhst_secret")
        result, output, _ = self.pair(outcome=station.BAD_CODE)
        self.assertEqual(0, result)
        self.assertIn("already paired", output)
        self.assertNotIn("mhst_secret", output)
        self.assertEqual("mhst_secret", station.load_key())

    def test_a_bad_code_lets_setup_finish_and_the_app_ask(self):
        result, output, _ = self.pair(outcome=station.BAD_CODE)
        self.assertEqual(setup_station.NOT_PAIRED, result)
        self.assertIn("new one", output)

    def test_an_outage_lets_setup_finish_and_the_app_ask(self):
        result, output, _ = self.pair(outcome=station.OFFLINE)
        self.assertEqual(setup_station.NOT_PAIRED, result)
        self.assertIn("Couldn't reach", output)

    def test_no_code_never_calls_the_website(self):
        result, _, pair = self.pair(code="")
        self.assertEqual(setup_station.NOT_PAIRED, result)
        pair.assert_not_called()

    def test_failed_install_stops_setup_before_pairing(self):
        error = setup_station.subprocess.CalledProcessError(1, "pip")
        with mock.patch.object(setup_station, "install", side_effect=error), \
                mock.patch.object(setup_station.subprocess, "run") as run, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(1, setup_station.main(["--environment", self.state]))
        run.assert_not_called()

    def test_an_existing_environment_is_kept_and_updated(self):
        folder = os.path.join(self.state, "environment")
        python = setup_station.environment_python(folder)
        os.makedirs(os.path.dirname(python))
        open(python, "w", encoding="utf-8").close()
        with mock.patch.object(setup_station.subprocess, "run") as run:
            self.assertEqual(python, setup_station.install(folder))
        run.assert_called_once()
        self.assertEqual(python, run.call_args[0][0][0])


class WebsiteTests(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.state, True)
        patcher = mock.patch.dict(os.environ, {"MAKERAUTH_STATE_DIR": self.state})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("MAKERAUTH_WEBSITE_URL", None)
        self.addCleanup(importlib.reload, station)

    def test_real_website_by_default(self):
        self.assertEqual(station.DEFAULT_WEBSITE_URL, station._website_url())

    def test_a_test_site_is_remembered_after_setup(self):
        with mock.patch.dict(os.environ, {"MAKERAUTH_WEBSITE_URL": "https://test-x.pantheonsite.io/"}):
            importlib.reload(station)
            station.remember_website()
        importlib.reload(station)
        self.assertEqual("https://test-x.pantheonsite.io", station.WEBSITE_URL)

    def test_pairing_with_the_real_website_forgets_a_test_site(self):
        path = station.state_path("website-url.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("https://test-x.pantheonsite.io")
        with mock.patch.dict(os.environ, {"MAKERAUTH_WEBSITE_URL": station.DEFAULT_WEBSITE_URL}):
            importlib.reload(station)
            station.remember_website()
        self.assertFalse(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
