"""Opens the website in a throwaway browser, so a member's login can't outlast their session.

A station's computer is shared, and members have no easy way to log out of a
website. So pages open in a separate Chrome or Edge with its own temporary
profile. Ending the session closes that browser and deletes the profile, and the
login goes with it, whether or not the member logged out. Any other browser
windows on the computer use a different profile and aren't touched.

If the app stopped before it could clean up, the next start of the login screen
does it. The profile folder is the only thing that identifies these browsers.
"""
import os
import shutil
import subprocess
import sys
import webbrowser

import psutil

import station

CLOSE_WAIT_SECONDS = 3


def profile_dir():
    return station.state_path("browser-session")


def _windows_candidates():
    roots = [os.environ.get(name) for name in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")]
    apps = [("Google", "Chrome", "Application", "chrome.exe"), ("Microsoft", "Edge", "Application", "msedge.exe")]
    return [os.path.join(root, *app) for app in apps for root in roots if root]


def find_browser():
    """Chrome or Edge, because they can run a separate profile and show a bare window."""
    override = os.environ.get("MAKERAUTH_BROWSER")
    if override:
        return override
    if sys.platform == "win32":
        return next((path for path in _windows_candidates() if os.path.exists(path)), None)
    names = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge")
    return next((path for path in map(shutil.which, names) if path), None)


def open_page(url, bare_window=False):
    """Open a page. Returns True if the login will be cleaned up when the session ends.

    A bare window has no tabs or address bar, for the chat page. False means no
    suitable browser was found, so the normal one was used and can't be cleaned up.
    """
    browser = find_browser()
    if not browser:
        webbrowser.open(url)
        return False
    target = [f"--app={url}"] if bare_window else ["--new-window", url]
    subprocess.Popen(
        [browser, f"--user-data-dir={profile_dir()}", "--no-first-run", "--no-default-browser-check",
         "--disable-sync"] + target,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


def _session_processes():
    marker = f"--user-data-dir={profile_dir()}"
    found = []
    for process in psutil.process_iter(["cmdline"]):
        try:
            if marker in (process.info["cmdline"] or []):
                found.append(process)
        except (psutil.Error, OSError):
            continue
    return found


def close_session():
    """Close the throwaway browser and delete its profile. Safe to call at any time."""
    processes = _session_processes()
    for process in processes:
        try:
            process.terminate()
        except psutil.Error:
            pass
    _gone, alive = psutil.wait_procs(processes, timeout=CLOSE_WAIT_SECONDS)
    for process in alive:
        try:
            process.kill()
        except psutil.Error:
            pass
    psutil.wait_procs(alive, timeout=CLOSE_WAIT_SECONDS)
    # A file can stay locked briefly on Windows. The next start tries again.
    shutil.rmtree(profile_dir(), ignore_errors=True)
    return not os.path.exists(profile_dir())
