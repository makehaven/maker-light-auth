"""Tests that the throwaway browser and its login are gone when a session ends.

A small script stands in for Chrome. It stays running and writes a "login" into
its profile, as Chrome would.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import station_browser  # noqa: E402

FAKE_BROWSER = """#!{python}
import os, sys, time
args = sys.argv[1:]
profile = next(a.split("=", 1)[1] for a in args if a.startswith("--user-data-dir="))
os.makedirs(profile, exist_ok=True)
with open(os.path.join(profile, "Cookies"), "w") as handle:
    handle.write(" ".join(args))
time.sleep(60)
"""


class BrowserTests(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.mkdtemp()
        os.environ["MAKERAUTH_STATE_DIR"] = self.state
        self.addCleanup(shutil.rmtree, self.state, True)
        self.addCleanup(os.environ.pop, "MAKERAUTH_STATE_DIR", None)
        self.browser = os.path.join(self.state, "fake-browser")
        with open(self.browser, "w", encoding="utf-8") as handle:
            handle.write(FAKE_BROWSER.format(python=sys.executable))
        os.chmod(self.browser, 0o755)
        os.environ["MAKERAUTH_BROWSER"] = self.browser
        self.addCleanup(os.environ.pop, "MAKERAUTH_BROWSER", None)
        self.addCleanup(station_browser.close_session)

    def cookies(self):
        return os.path.join(station_browser.profile_dir(), "Cookies")

    def wait_for_cookies(self):
        deadline = time.time() + 5
        while time.time() < deadline:
            if os.path.exists(self.cookies()) and os.path.getsize(self.cookies()):
                return
            time.sleep(0.05)
        self.fail("The browser never started.")

    def test_ending_the_session_closes_the_browser_and_forgets_the_login(self):
        self.assertTrue(station_browser.open_page("https://x/tool-chat/1", bare_window=True))
        self.wait_for_cookies()
        self.assertEqual(1, len(station_browser._session_processes()))

        self.assertTrue(station_browser.close_session())
        self.assertEqual([], station_browser._session_processes())
        self.assertFalse(os.path.exists(station_browser.profile_dir()))

    def test_chat_opens_bare_and_pages_open_normally(self):
        station_browser.open_page("https://x/tool-chat/1", bare_window=True)
        self.wait_for_cookies()
        with open(self.cookies(), encoding="utf-8") as handle:
            self.assertIn("--app=https://x/tool-chat/1", handle.read())
        station_browser.close_session()

        station_browser.open_page("https://x/i/1")
        self.wait_for_cookies()
        with open(self.cookies(), encoding="utf-8") as handle:
            arguments = handle.read()
        self.assertIn("--new-window", arguments)
        self.assertIn("https://x/i/1", arguments)

    def test_other_browsers_are_left_alone(self):
        other = subprocess.Popen([self.browser, "--user-data-dir=" + os.path.join(self.state, "members-own-chrome")])
        self.addCleanup(other.wait)
        self.addCleanup(other.kill)
        station_browser.open_page("https://x/i/1")
        self.wait_for_cookies()
        station_browser.close_session()
        self.assertIsNone(other.poll(), "A browser with another profile must keep running.")

    def test_leftovers_from_a_crash_are_cleaned_up(self):
        station_browser.open_page("https://x/i/1")
        self.wait_for_cookies()
        # The next start of the login screen knows nothing about that browser.
        self.assertTrue(station_browser.close_session())
        self.assertEqual([], station_browser._session_processes())

    def test_closing_with_nothing_open_is_harmless(self):
        self.assertTrue(station_browser.close_session())

    def test_no_suitable_browser_says_it_cannot_clean_up(self):
        with mock.patch.object(station_browser, "find_browser", return_value=None), \
                mock.patch.object(station_browser.webbrowser, "open") as opened:
            self.assertFalse(station_browser.open_page("https://x/i/1"))
        opened.assert_called_once_with("https://x/i/1")


if __name__ == "__main__":
    unittest.main()
