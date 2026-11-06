# MakerAuth: access station for a tool or room

`maker-light-auth.pyw` is the full-screen login for a computer that unlocks a tool or room. A member scans an RFID tag or enters an email, the station checks their badge, and a session timer runs until they end it.

**Nothing about a station is configured on the computer.** Every computer runs the same code. What each one does is set on the website, and a one-time pairing code tells a computer which station it is.

## Setting up a station

1. On the website, go to `/admin/config/system/access-stations`, add the station (name, source ID, permission, equipment, messages) and click **Pairing code**. Codes last one hour and work once.
2. On the computer, install Python 3.8 or newer with Tk, then the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

   On Ubuntu, also install `python3-tk`.
3. Run `python maker-light-auth.pyw` (on Windows, `pythonw` hides the console) and enter the code.

To start it automatically on Windows, press Win + R, type `shell:startup`, and put a shortcut to the script in that folder for the shared account.

Type `exit` at the prompt to close the program. Once a session has started, click **End Session** first.

### Replacing or moving a computer

Issue a new pairing code and enter it on the new computer. The old computer keeps working until the code is redeemed, then its key stops working. To cut a computer off immediately, use **Unpair** or disable the station on the website.

## How it works

| What | Where it comes from |
|---|---|
| Permission, station name, messages, ending screen, rating on/off | Station config from the website |
| Reservations and materials | Station config, fetched when the app starts (so after every session) and every 15 minutes |
| Access box address | Site-wide setting on the website, sent in the station config |
| Tool status and maintenance notes | The tool's status on the website, sent in the station config and shown above the login prompt |
| Which station this is | The saved key |

**Member lookups** try the building's access box first, then the website. The box's 403 or 404 is final, because the box has already asked the website when its own copy can't answer. If the box can't answer at all, the website is asked. The station's key goes only to the website, never to the box, because lookups to the box are plain HTTP on the LAN.

**During a website outage** the station runs on its saved config. Card logins keep working through the box. Email logins need the website unless the box's copy includes member emails, so the station tells members to use their card. The ending screen uses no network apart from material photos, which it skips if it can't load them.

**Reporting a problem** is available from the session timer and the ending screen. A tool problem goes through the website's equipment report, so it emails staff, posts to Slack and puts the tool in Reported Concern for staff to confirm. A software or computer problem names no tool, so it can't change the tool's status. A station with no linked tool only offers those. During an outage, reports are saved and sent when the website is back.

**Reservations.** Someone else's reservation shows as a warning above the login prompt from an hour ahead, and on the session timer from 30 minutes ahead. It never ends a session. The timer keeps checking the website during a session, so it hears about a reservation made after the member logged in.

**Ask.** The timer's Ask button leads to the tool's chat-only page on the website, by QR code on the member's phone or on this computer, and to the tool's page. The chat needs a MakeHaven login. On this computer pages open in a separate Chrome or Edge with a temporary profile, and ending the session closes it and deletes the profile, so the login can't reach the next person. Other browser windows aren't touched. If neither browser is installed, the normal browser opens and the ending screen asks the member to log out. A station with no tool has no Ask button.

**The access log.** Every member lookup appears in the website's access log under the station's source ID, with method `MakerAuth`, including lookups answered by the box, which forwards them. Session end, ratings and reset choices are only in this computer's `SessionLog.csv`.

The website records each config request as a check-in, so its stations list shows when each computer was last seen and which app version it runs.

## Files on each computer

These live outside the app folder, so updating the code can't touch them. On Windows the folder is `%LOCALAPPDATA%\MakerAuth`; on Linux it is `~/.config/makerauth`.

| File | Purpose |
|---|---|
| `station.key` | This station's key. Treat it like a password. |
| `station-config.json` | The last config the website sent |
| `SessionLog.csv` | Sessions, ratings and reset choices on this computer |
| `pending-reports.json` | Problem reports waiting for the website to come back |
| `browser-session` | The temporary browser profile, deleted when a session ends |

## Settings for testing

| Environment variable | Effect |
|---|---|
| `MAKERAUTH_WEBSITE_URL` | Use another website, such as a Pantheon test environment |
| `MAKERAUTH_STATE_DIR` | Keep the key, config and log in another folder |
| `MAKERAUTH_BROWSER` | Use this browser for pages opened during a session |
| `MAKERAUTH_DEBUG=1` | Show a debug log on screen. It displays member emails, so never leave it on at a station. |

## Tests

```bash
python -m unittest discover -s tests
```

## Moving a station from the old `config.ini`

1. Create and pair the station on the website as above. Use the same source ID so its access log stays continuous.
2. Update the code. `config.ini` is no longer used and can be deleted. If git refuses to update because the file has local edits, save a copy and delete it first.
3. Check the old `config.ini` first: if `require_usage_input` was `true`, tell whoever is doing the rollout, because the usage input screen has been removed.
