"""What makes this computer a station: its key, its saved config, and its lookups.

Nothing about a station is configured on the computer. Staff describe it on the
website (/admin/config/system/access-stations) and it pairs once with a one-time
code. After that this computer holds only two files in its state directory: the
key, and the last config the website sent, which is what the station runs on
when the website is down.

No GUI code lives here, so all of it can be tested without a display.
"""
import csv
import json
import os
import sys
import tempfile
from datetime import datetime
from urllib.parse import quote

import requests

VERSION = "2.0.0"
WEBSITE_URL = os.environ.get("MAKERAUTH_WEBSITE_URL", "https://www.makehaven.org").rstrip("/")
DEBUG = os.environ.get("MAKERAUTH_DEBUG", "") == "1"

# Seconds to wait before giving up, so an outage can't freeze the station. The
# box answers from its own copy and allows itself 2.5s to ask the website.
WEBSITE_TIMEOUT = 10
LOCAL_TIMEOUT = 5

# Some website routes have only ever been called with this User-Agent.
USER_AGENT = "curl/7.68.0"

# Outcomes of talking to the website about this station.
OK = "ok"
REVOKED = "revoked"
BAD_CODE = "bad_code"
OFFLINE = "offline"

# Outcomes of sending a problem report.
REPORT_SENT = "sent"
REPORT_SAVED = "saved"
REPORT_REJECTED = "rejected"

# The keys are the website's own: its report webform uses the tool ones as options.
TOOL_ISSUES = [
    ("broken_nonfuctional", "Broken, not working"),
    ("damaged_functional", "Damaged, but still works"),
    ("parts_missing", "Missing parts"),
    ("supplies_missing", "Out of supplies"),
]
STATION_ISSUES = [
    ("software", "Software problem"),
    ("computer", "Problem with this computer"),
    ("other", "Something else"),
]
LONGEST_NOTE = 240

LOG_HEADER = ["Timestamp", "Action", "First Name", "Last Name", "Permission", "Station", "Duration", "Rating", "Details"]


def state_dir():
    """The per-machine folder, created on first use and kept out of the app folder."""
    path = os.environ.get("MAKERAUTH_STATE_DIR")
    if not path:
        if sys.platform == "win32":
            base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
            path = os.path.join(base, "MakerAuth")
        else:
            base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
            path = os.path.join(base, "makerauth")
    os.makedirs(path, exist_ok=True)
    return path


def state_path(name):
    return os.path.join(state_dir(), name)


def _write_private(name, text):
    """Replace a state file in one step, so a power cut can't leave half of it."""
    fd, tmp = tempfile.mkstemp(dir=state_dir(), prefix=name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, state_path(name))
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def load_key():
    try:
        with open(state_path("station.key"), encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return ""


def save_key(key):
    _write_private("station.key", key)


def forget_key():
    try:
        os.remove(state_path("station.key"))
    except OSError:
        pass


def load_saved_config():
    """The last config the website sent, or None if there isn't a usable one."""
    try:
        with open(state_path("station-config.json"), encoding="utf-8") as handle:
            config = json.load(handle)
    except (OSError, ValueError):
        return None
    return config if isinstance(config, dict) else None


def save_config(config):
    _write_private("station-config.json", json.dumps(config))


def _headers(key=None):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Cache-Control": "no-cache",
        "X-Station-Version": VERSION,
    }
    if key:
        headers["X-API-Key"] = key
    return headers


def pair(code):
    """Swap a pairing code for this station's key. Returns (outcome, config)."""
    try:
        response = requests.post(
            f"{WEBSITE_URL}/api/v0/station/pair",
            json={"code": code},
            headers=_headers(),
            timeout=WEBSITE_TIMEOUT,
        )
    except requests.RequestException:
        return OFFLINE, None
    if response.status_code in (400, 403):
        return BAD_CODE, None
    try:
        body = response.json()
        key, config = body["key"], body["config"]
    except (ValueError, KeyError, TypeError):
        return OFFLINE, None
    if response.status_code != 200 or not key or not isinstance(config, dict):
        return OFFLINE, None
    save_key(key)
    save_config(config)
    return OK, config


def fetch_config(key):
    """Ask the website for this station's setup. Also its heartbeat.

    Returns (outcome, config). Only a 401 means the station is revoked; anything
    else that goes wrong is an outage, and the saved config stays in charge.
    """
    try:
        response = requests.get(
            f"{WEBSITE_URL}/api/v0/station/config",
            headers=_headers(key),
            timeout=WEBSITE_TIMEOUT,
        )
    except requests.RequestException:
        return OFFLINE, None
    if response.status_code == 401:
        return REVOKED, None
    if response.status_code != 200:
        return OFFLINE, None
    try:
        config = response.json()
    except ValueError:
        return OFFLINE, None
    if not isinstance(config, dict) or "station" not in config:
        return OFFLINE, None
    save_config(config)
    return OK, config


def permission_id(config):
    return ((config or {}).get("station") or {}).get("permission_id") or ""


def source_id(config):
    return ((config or {}).get("station") or {}).get("source_id") or ""


def local_url(config):
    return (((config or {}).get("access") or {}).get("local_url") or "").rstrip("/")


def _box_answered(response):
    """True when the box gave a real verdict, not just some HTTP response.

    A 403 or 404 is a verdict: the box has already asked the website when its
    copy can't answer, so asking again would log the same tap twice. A 200 must
    hold a list of records. Everything else (401, 400 for a badge it hasn't
    synced, 5xx, or an error page from something else on that address) means
    this source can't answer, so the website gets asked.
    """
    if response.status_code in (403, 404):
        return True
    if response.status_code != 200:
        return False
    try:
        body = response.json()
    except ValueError:
        return False
    return isinstance(body, list)


def check_access(identifier, is_email, config, key):
    """Ask for a member's verdict: the box first, then the website.

    Returns the response that answered, or None if nothing could. The station
    stays locked on None. The key only ever goes to the website: lookups to the
    box travel over plain HTTP on the LAN, and the box doesn't want a key.
    """
    endpoint = "email" if is_email else "serial"
    path = (
        f"/api/v0/{endpoint}/{quote(identifier, safe='')}"
        f"/permission/{quote(permission_id(config), safe='')}"
    )
    params = {"source": source_id(config), "method": "MakerAuth"}

    box = local_url(config)
    if box:
        try:
            response = requests.get(box + path, params=params, headers=_headers(), timeout=LOCAL_TIMEOUT)
            if _box_answered(response):
                return response
        except requests.RequestException:
            pass

    try:
        return requests.get(WEBSITE_URL + path, params=params, headers=_headers(key), timeout=WEBSITE_TIMEOUT)
    except requests.RequestException:
        return None


def denial_reason(response):
    """The sources explain a 403 in {"error": "..."}; fall back to a generic message."""
    try:
        reason = response.json().get("error")
    except (ValueError, AttributeError):
        reason = None
    if response.status_code == 404:
        return "Denied: account not recognized. Check your email or card."
    if reason:
        return f"Denied: {reason}"
    return "Access denied."


def upcoming_reservations(config, now=None):
    """Reservations that haven't ended, with "in progress" worked out from this clock.

    The config can be many minutes old, or hours during an outage, so what it says
    about "now" is out of date. Only the start and end times can be trusted.
    """
    now = now or datetime.now().astimezone()
    kept = []
    for reservation in (config or {}).get("reservations") or []:
        current = dict(reservation)
        try:
            if datetime.fromisoformat(reservation["end"]) <= now:
                continue
            current["in_progress"] = datetime.fromisoformat(reservation["start"]) <= now
        except (KeyError, TypeError, ValueError):
            pass
        kept.append(current)
    return kept


def display_signature(config, website_up, now=None):
    """Everything the login screen draws. If this hasn't changed, don't redraw it."""
    shown = {key: value for key, value in (config or {}).items() if key not in ("server_time", "reservations")}
    shown["reservations"] = upcoming_reservations(config, now)
    shown["website_up"] = website_up
    return json.dumps(shown, sort_keys=True)


def _clock(moment):
    hour = moment.hour % 12 or 12
    return f"{hour}:{moment.minute:02d} {'AM' if moment.hour < 12 else 'PM'}"


def reservation_parts(reservation):
    """A reservation's (title, when, who) as screen text."""
    try:
        start = datetime.fromisoformat(reservation["start"])
        end = datetime.fromisoformat(reservation["end"])
        when = f"{start.strftime('%a %b')} {start.day}, {_clock(start)} to {_clock(end)}"
    except (KeyError, TypeError, ValueError):
        when = "Time unknown"
    title = reservation.get("equipment") or "Reservation"
    who = " · ".join(part for part in (reservation.get("member"), reservation.get("purpose")) if part)
    return title, when, who


def status_notices(config):
    """What members should know about the tools here, as (kind, text), worst first."""
    notices = []
    for item in (config or {}).get("equipment") or []:
        status = item.get("status") or {}
        level = status.get("level") or "ok"
        if level == "ok":
            continue
        title = item.get("title") or "This tool"
        if status.get("label") == "Reported Concern":
            text = f"{title}: a problem was reported. Staff are checking it."
        else:
            text = f"{title}: {status.get('label') or 'Not fully working'}."
            note = (status.get("note") or "").strip()
            if note:
                text += " " + (note if len(note) <= LONGEST_NOTE else note[:LONGEST_NOTE].rstrip() + "...")
            back = _short_date(status.get("expected_back"))
            if back:
                text += f" Expected back {back}."
        notices.append(("bad" if level == "down" else "warn", text))
    return sorted(notices, key=lambda notice: notice[0] != "bad")


def _short_date(value):
    try:
        moment = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return ""
    return f"{moment.strftime('%b')} {moment.day}"


def issue_choices(config):
    """A station with a tool asks about the tool first, then its computer."""
    return (TOOL_ISSUES if (config or {}).get("equipment") else []) + STATION_ISSUES


def is_tool_issue(issue):
    return issue in (key for key, _label in TOOL_ISSUES)


def _post_report(report, key):
    """Returns (outcome, reason). Only a clear refusal stops it being tried again."""
    try:
        response = requests.post(
            f"{WEBSITE_URL}/api/v0/station/report",
            json=report,
            headers=_headers(key),
            timeout=WEBSITE_TIMEOUT,
        )
    except requests.RequestException:
        return REPORT_SAVED, ""
    if response.status_code == 200:
        return REPORT_SENT, ""
    if response.status_code == 400:
        try:
            return REPORT_REJECTED, response.json().get("error") or ""
        except (ValueError, AttributeError):
            return REPORT_REJECTED, ""
    return REPORT_SAVED, ""


def _load_pending_reports():
    try:
        with open(state_path("pending-reports.json"), encoding="utf-8") as handle:
            pending = json.load(handle)
    except (OSError, ValueError):
        return []
    return pending if isinstance(pending, list) else []


def submit_report(report):
    """Send a report, or keep it to send later. A member's report must not be lost."""
    outcome, reason = _post_report(report, load_key())
    if outcome == REPORT_SAVED:
        _write_private("pending-reports.json", json.dumps(_load_pending_reports() + [report]))
    return outcome, reason


def send_pending_reports():
    """Try the saved reports again, oldest first, stopping at the first that can't go."""
    pending = _load_pending_reports()
    if not pending:
        return
    key = load_key()
    while pending and _post_report(pending[0], key)[0] != REPORT_SAVED:
        pending.pop(0)
    _write_private("pending-reports.json", json.dumps(pending))


def log_event(action, user_info=None, duration="", rating="", details=""):
    """Add a line to this computer's session log. Never allowed to stop a session."""
    user_info = user_info or {}
    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        action,
        user_info.get("first_name", "Unknown"),
        user_info.get("last_name", "Unknown"),
        user_info.get("permission", ""),
        user_info.get("station", ""),
        duration,
        rating,
        details,
    ]
    try:
        path = state_path("SessionLog.csv")
        is_new = not os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if is_new:
                writer.writerow(LOG_HEADER)
            writer.writerow(row)
    except OSError as error:
        print(f"Could not write the session log: {error}")
