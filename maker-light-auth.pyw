"""The station's login screen. Everything it shows comes from the website.

Run with no setup: an unpaired computer asks for a pairing code, and a paired
one fetches its config and falls back to the saved copy if the website is down.
Type "exit" in the box to close the program.
"""
import queue
import threading
import tkinter as tk

import station
import theme
from session_timer import SessionTimerWindow

RESULT_SHOWN_MS = 15000
FOCUS_CHECK_MS = 2000
NO_CONFIG_RETRY_MS = 5000
CLOCK_CHECK_MS = 30000
DEFAULT_REFRESH_SECONDS = 900
MAX_RESERVATIONS_SHOWN = 5

LOGIN_HEADING = "Tap your card on the scanner box"
LOGIN_HINT = "No card? Type your email below and press Enter."
PAIR_HEADING = "Set up this station"
PAIR_HINT = "Enter the pairing code from staff, then press Enter."

key = ""
config = None
website_up = True
revoked = False
pairing = False
status_generation = 0
drawn_signature = None
session_user = None  # Set when a member is let in; the timer opens once this window is gone

root = tk.Tk()
root.title("MakerAuth")
root.attributes("-fullscreen", True)  # Keep the window in fullscreen mode
root.attributes("-topmost", True)     # Make the window always stay on top
root.protocol("WM_DELETE_WINDOW", lambda: None)  # Only "exit" in the box closes it
ui = theme.Theme(root)

station_label = ui.header(root)
offline_banner = tk.Label(root, text="The website isn't answering. Showing saved information.",
                          bg=theme.WARNING, fg=theme.INK, font=ui.font(14, True), pady=ui.px(8))

debug_box = None
if station.DEBUG:
    debug_box = tk.Text(root, height=8, font=ui.font(11))
    debug_box.pack(side="bottom", fill="x")

body = tk.Frame(root, bg=theme.PAGE)
body.pack(fill="both", expand=True, padx=ui.px(40), pady=ui.px(32))
body.grid_rowconfigure(0, weight=1)
body.grid_columnconfigure(0, weight=5, uniform="side")

login_card = ui.card(body, pad=36)
login_inner = tk.Frame(login_card, bg=theme.CARD)
login_inner.pack(expand=True, fill="x")

notices_frame = tk.Frame(login_inner, bg=theme.CARD)
heading_label = tk.Label(login_inner, text="Starting...", bg=theme.CARD, fg=theme.INK,
                         font=ui.font(30, True), wraplength=ui.px(600), justify="left", anchor="w")
heading_label.pack(fill="x")
hint_label = tk.Label(login_inner, bg=theme.CARD, fg=theme.MUTED, font=ui.font(16),
                      wraplength=ui.px(600), justify="left", anchor="w")
hint_label.pack(fill="x", pady=(ui.px(8), ui.px(22)))

# The border and padding are frames, because an Entry draws its text and cursor
# right against its own edge.
entry_border = tk.Frame(login_inner, bg=theme.BRAND, padx=ui.px(2), pady=ui.px(2))
entry_border.pack(fill="x")
entry_padding = tk.Frame(entry_border, bg="#ffffff", padx=ui.px(16), pady=ui.px(14))
entry_padding.pack(fill="x")
entry = tk.Entry(entry_padding, font=ui.font(30), bg="#ffffff", fg=theme.INK, insertbackground=theme.BRAND,
                 insertwidth=ui.px(3), relief="flat", bd=0, highlightthickness=0, disabledbackground="#ffffff")
entry.pack(fill="x")

status_label = tk.Label(login_inner, font=ui.font(18, True), wraplength=ui.px(600), justify="left", anchor="w",
                        padx=ui.px(16), pady=ui.px(12))
welcome_label = tk.Label(login_inner, bg=theme.CARD, fg=theme.MUTED, font=ui.font(15),
                         wraplength=ui.px(600), justify="left", anchor="w")



def fit_text_to_card(event):
    """Wrap to the card's real width, which depends on the screen and the layout."""
    for label in (heading_label, hint_label, welcome_label):
        label.config(wraplength=event.width)
    inside = max(1, event.width - 2 * ui.px(16))
    status_label.config(wraplength=inside)
    for label in notices_frame.winfo_children():
        label.config(wraplength=inside)


login_inner.bind("<Configure>", fit_text_to_card)

reservations_card = ui.card(body, pad=24)
tk.Label(reservations_card, text="Upcoming reservations", bg=theme.CARD, fg=theme.INK, font=ui.font(20, True),
         anchor="w").pack(fill="x", pady=(0, ui.px(12)))
reservations_list = tk.Frame(reservations_card, bg=theme.CARD)
reservations_list.pack(fill="both", expand=True)


def add_debug_message(message):
    if debug_box is not None:
        debug_box.insert(tk.END, message + "\n")
        debug_box.see(tk.END)


def set_status(message, kind="info", clear=True):
    """Show a result under the box. Results clear so nobody's denial stays on screen."""
    global status_generation
    status_generation += 1
    background, foreground = theme.STATUS[kind]
    status_label.config(text=message, bg=background, fg=foreground)
    status_label.pack(fill="x", pady=(ui.px(18), 0), before=welcome_label) if welcome_label.winfo_ismapped() \
        else status_label.pack(fill="x", pady=(ui.px(18), 0))
    root.update()
    add_debug_message(f"Status: {message}")
    if clear:
        generation = status_generation
        root.after(RESULT_SHOWN_MS, lambda: clear_status(generation))


def clear_status(generation=None):
    if generation is None or generation == status_generation:
        status_label.pack_forget()


def enable_entry():
    entry.config(state="normal")
    entry.delete(0, tk.END)
    entry.focus_force()


def keep_focus():
    """A card reader types like a keyboard, so a scan is lost if the box loses focus."""
    if str(entry.cget("state")) == "normal" and root.focus_get() is not entry:
        entry.focus_force()
    root.after(FOCUS_CHECK_MS, keep_focus)


def submit(_event=None):
    value = entry.get().strip()
    if not value or str(entry.cget("state")) != "normal":
        return
    entry.delete(0, tk.END)
    if value.lower() == "exit":
        root.destroy()
    elif pairing:
        try_pairing_code(value)
    else:
        handle_access(value)


entry.bind("<Return>", submit)
entry.bind("<KP_Enter>", submit)


def show_config():
    """Draw everything that depends on the config, for the first time or after a refresh."""
    details = config.get("station") or {}
    display = config.get("display") or {}
    station_label.config(text=" · ".join(part for part in (details.get("name"), details.get("area")) if part))

    if website_up:
        offline_banner.pack_forget()
    else:
        offline_banner.pack(fill="x", before=body)

    draw_status_notices()

    welcome = display.get("welcome_message") or ""
    welcome_label.config(text=welcome)
    if welcome:
        welcome_label.pack(fill="x", pady=(ui.px(22), 0))
    else:
        welcome_label.pack_forget()

    if display.get("show_reservations", True):
        body.grid_columnconfigure(1, weight=4, uniform="side")
        reservations_card.grid(row=0, column=1, sticky="nsew", padx=(ui.px(28), 0))
        draw_reservations()
    else:
        reservations_card.grid_forget()
        body.grid_columnconfigure(1, weight=0, uniform="")


def redraw_if_changed():
    """Redrawing rebuilds widgets, which flashes, so only do it for a real change."""
    global drawn_signature
    signature = station.display_signature(config, website_up)
    if signature != drawn_signature:
        drawn_signature = signature
        add_debug_message("Redrew the screen.")
        show_config()


def check_clock():
    """A reservation can start or end between website checks. No network involved."""
    if config and not pairing:
        redraw_if_changed()
    root.after(CLOCK_CHECK_MS, check_clock)


def website_answering():
    """Check before blaming a member: the last website check can be minutes old."""
    global website_up
    if website_up and station.fetch_config(key)[0] == station.OFFLINE:
        website_up = False
        redraw_if_changed()
    return website_up


def draw_status_notices():
    """Tool status goes above the prompt, so it's read before anyone starts."""
    for widget in notices_frame.winfo_children():
        widget.destroy()
    notices = station.status_notices(config)
    if not notices:
        notices_frame.pack_forget()
        return
    notices_frame.pack(fill="x", before=heading_label, pady=(0, ui.px(24)))
    width = max(1, login_inner.winfo_width() - 2 * ui.px(16)) if login_inner.winfo_width() > 1 else ui.px(560)
    for kind, text in notices:
        background, foreground = theme.STATUS[kind]
        tk.Label(notices_frame, text=text, bg=background, fg=foreground, font=ui.font(17, True), anchor="w",
                 justify="left", wraplength=width, padx=ui.px(16), pady=ui.px(12)).pack(fill="x", pady=(0, ui.px(6)))


def draw_reservations():
    for widget in reservations_list.winfo_children():
        widget.destroy()
    reservations = station.upcoming_reservations(config)
    if not reservations:
        tk.Label(reservations_list, text="Nothing booked in the next 7 days.", bg=theme.CARD, fg=theme.MUTED,
                 font=ui.font(15), anchor="w").pack(fill="x")
        return
    for reservation in reservations[:MAX_RESERVATIONS_SHOWN]:
        draw_reservation(reservation)
    hidden = len(reservations) - MAX_RESERVATIONS_SHOWN
    if hidden > 0:
        tk.Label(reservations_list, text=f"and {hidden} more", bg=theme.CARD, fg=theme.MUTED,
                 font=ui.font(14), anchor="w").pack(fill="x", pady=(ui.px(4), 0))


def draw_reservation(reservation):
    live = reservation.get("in_progress")
    row = tk.Frame(reservations_list, bg=theme.PAGE)
    row.pack(fill="x", pady=(0, ui.px(10)))
    tk.Frame(row, bg=theme.GOLD if live else theme.BRAND, width=ui.px(5)).pack(side="left", fill="y")
    text = tk.Frame(row, bg=theme.PAGE, padx=ui.px(14), pady=ui.px(10))
    text.pack(side="left", fill="x", expand=True)
    title, when, who = station.reservation_parts(reservation)
    line = tk.Frame(text, bg=theme.PAGE)
    line.pack(fill="x")
    tk.Label(line, text=when, bg=theme.PAGE, fg=theme.INK, font=ui.font(15, True), anchor="w").pack(side="left")
    if live:
        tk.Label(line, text=" In progress ", bg=theme.GOLD, fg=theme.INK, font=ui.font(11, True)).pack(side="right")
    detail = " · ".join(part for part in (title, who) if part)
    if detail:
        tk.Label(text, text=detail, bg=theme.PAGE, fg=theme.MUTED, font=ui.font(14), anchor="w",
                 wraplength=ui.px(420), justify="left").pack(fill="x", pady=(ui.px(2), 0))


def schedule_refresh():
    seconds = (config or {}).get("refresh_seconds") or DEFAULT_REFRESH_SECONDS
    root.after(int(seconds) * 1000, start_refresh)


def start_refresh():
    """Ask the website on another thread, so an outage never freezes the screen."""
    results = queue.Queue()


    def check_website():
        outcome = station.fetch_config(key)
        results.put(outcome)
        if outcome[0] == station.OK:
            station.send_pending_reports()

    threading.Thread(target=check_website, daemon=True).start()
    root.after(200, finish_refresh, results)


def finish_refresh(results):
    global config, website_up, revoked
    try:
        outcome, fresh = results.get_nowait()
    except queue.Empty:
        root.after(200, finish_refresh, results)
        return
    if outcome == station.OK:
        config = fresh
        website_up = True
    elif outcome == station.REVOKED:
        # Stops logins through the box as well, which doesn't know about this.
        revoked = True
    else:
        website_up = False
    add_debug_message(f"Config refresh: {outcome}")
    if revoked:
        show_pairing("This station is no longer set up. Ask staff for a new pairing code.", "bad")
        return
    if not pairing:
        redraw_if_changed()
    schedule_refresh()


def handle_access(identifier):
    if not station.permission_id(config):
        set_status("This station has no permission set on the website. Please tell staff.", "bad")
        return
    entry.config(state="disabled")
    set_status("Checking...", "info", clear=False)
    try:
        is_email = "@" in identifier
        response = station.check_access(identifier, is_email, config, key)
        if response is None:
            add_debug_message("No source answered.")
            set_status("Can't reach the access system. Please try again in a moment.", "warn")
        else:
            add_debug_message(f"{response.request.url} -> {response.status_code}: {response.text}")
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and data:
                    process_access_granted(data)
                    return
                set_status("Access denied.", "bad")
            elif response.status_code == 401:
                # The website refused this station, not the member. Stays locked.
                set_status("This station's website key isn't recognized. Please tell staff.", "bad")
            elif response.status_code == 404 and is_email and not website_answering():
                # The box may hold no emails, and can't ask the website right now.
                set_status("Email sign-in needs the website, which isn't answering. Please use your card.", "warn")
            elif response.status_code in (403, 404):
                set_status(station.denial_reason(response), "bad")
            else:
                set_status("Failed to contact server or access denied.", "bad")
    except Exception as e:
        # Never leave the station without a login prompt.
        add_debug_message(f"Error handling access: {e}")
        set_status("Something went wrong. Please try again.", "bad")
    enable_entry()


def process_access_granted(data):
    """Handle processing for users granted access."""
    user_info = {
        'first_name': data[0].get('first_name'),
        'last_name': data[0].get('last_name'),
        'permission': station.permission_id(config),
        'station': station.source_id(config),
        'uuid': data[0].get('uuid'),
    }
    set_status(f"Welcome, {user_info['first_name']} {user_info['last_name']}.", "ok", clear=False)
    root.after(1500, lambda: close_and_start_session(user_info))


def close_and_start_session(user_info):
    global session_user
    station.log_event("start", user_info)
    session_user = user_info
    for pending in root.tk.splitlist(root.tk.call("after", "info")):
        root.after_cancel(pending)
    root.destroy()


def show_login():
    global pairing
    pairing = False
    heading_label.config(text=LOGIN_HEADING)
    hint_label.config(text=LOGIN_HINT)
    clear_status()
    enable_entry()


def show_pairing(message=None, kind="info"):
    """Revoking forgets the key, because it can't be used again."""
    global pairing, revoked
    if revoked:
        station.forget_key()
        revoked = False
    pairing = True
    heading_label.config(text=PAIR_HEADING)
    hint_label.config(text=PAIR_HINT)
    enable_entry()
    if message:
        set_status(message, kind, clear=False)
    else:
        clear_status()


def try_pairing_code(code):
    global key, config, website_up
    entry.config(state="disabled")
    set_status("Pairing...", "info", clear=False)
    outcome, paired = station.pair(code)
    if outcome == station.OK:
        key = station.load_key()
        config = paired
        website_up = True
        run_station()
        return
    if outcome == station.BAD_CODE:
        set_status("That code is wrong or has expired. Ask staff for a new one.", "bad", clear=False)
    else:
        set_status("Can't reach the website to pair. Check the network and try again.", "warn", clear=False)
    enable_entry()


def wait_for_config():
    """Paired, but the website is down and this computer has never saved a config."""
    global config, website_up
    outcome, fresh = station.fetch_config(key)
    if outcome == station.OK:
        config = fresh
        website_up = True
        run_station()
    elif outcome == station.REVOKED:
        station.forget_key()
        show_pairing("This station is no longer set up. Ask staff for a new pairing code.", "bad")
    else:
        heading_label.config(text="Setting up this station")
        hint_label.config(text="Waiting for the website to answer.")
        root.after(NO_CONFIG_RETRY_MS, wait_for_config)


def run_station():
    show_login()
    redraw_if_changed()
    schedule_refresh()


def start():
    global key, config, website_up
    root.update()
    key = station.load_key()
    if not key:
        show_pairing()
        return
    outcome, fresh = station.fetch_config(key)
    if outcome == station.OK:
        config = fresh
        threading.Thread(target=station.send_pending_reports, daemon=True).start()
        run_station()
    elif outcome == station.REVOKED:
        station.forget_key()
        show_pairing("This station is no longer set up. Ask staff for a new pairing code.", "bad")
    else:
        website_up = False
        config = station.load_saved_config()
        if config:
            run_station()
        else:
            wait_for_config()


login_card.grid(row=0, column=0, sticky="nsew")
entry.config(state="disabled")
root.after(100, start)
root.after(FOCUS_CHECK_MS, keep_focus)
root.after(CLOCK_CHECK_MS, check_clock)
root.mainloop()

if session_user:
    SessionTimerWindow(session_user).run()
