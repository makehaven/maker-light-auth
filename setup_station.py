"""Finishes setting up this computer as a station.

The setup file from the website gets Python and this app onto the computer, then
runs this. It keeps the Windows-only steps to itself and leaves the rest here:
install what the app needs into its own environment, then swap the one-time code
for this station's key.

A code that doesn't work doesn't stop the setup. The app asks for one when it
starts, so a new code from the website still finishes the job.
"""
import argparse
import os
import subprocess
import sys

CODE_VARIABLE = "MAKERAUTH_PAIRING_CODE"
APP_DIR = os.path.dirname(os.path.abspath(__file__))

NOT_PAIRED = 2


def environment_python(folder):
    if sys.platform == "win32":
        return os.path.join(folder, "Scripts", "python.exe")
    return os.path.join(folder, "bin", "python")


def install(folder):
    """Make the app's environment, or bring an existing one up to date."""
    python = environment_python(folder)
    if not os.path.exists(python):
        subprocess.run([sys.executable, "-m", "venv", folder], check=True)
    subprocess.run(
        [python, "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
         "-r", os.path.join(APP_DIR, "requirements.txt")],
        check=True,
    )
    return python


def pair_this_computer():
    """Runs inside the environment, because it needs the app's dependencies."""
    import station

    code = os.environ.get(CODE_VARIABLE, "").strip()
    outcome, config = station.pair(code) if code else (station.BAD_CODE, None)
    if outcome == station.OK:
        station.remember_website()
        print(f"Paired as {(config.get('station') or {}).get('name') or 'this station'}.")
        return 0
    if station.load_key():
        print("The code wasn't used. This computer is already paired, so it stays as it was.")
        return 0
    if outcome == station.OFFLINE:
        print("Couldn't reach the website to pair. The app will ask for a code when it starts.")
    else:
        print("That code is wrong, used or expired. Make a new one on the website and type it into the app.")
    return NOT_PAIRED


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", help="Folder for the app's Python environment")
    parser.add_argument("--pair", action="store_true", help="Only pair. Needs the environment's Python.")
    options = parser.parse_args(arguments)
    if options.pair:
        return pair_this_computer()
    if not options.environment:
        parser.error("--environment is required")
    try:
        python = install(options.environment)
    except subprocess.CalledProcessError as error:
        print(f"Installing what the app needs failed: {error}")
        return 1
    return subprocess.run([python, os.path.abspath(__file__), "--pair"]).returncode


if __name__ == "__main__":
    sys.exit(main())
