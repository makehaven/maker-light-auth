import datetime
import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk

import help_panel
import report_form
import station
import station_browser
import theme


WARNING_CHECK_MS = 30000
DEFAULT_REFRESH_SECONDS = 900


class SessionTimerWindow:
    def __init__(self, user_info=None):
        if user_info is None:
            user_info = {'first_name': 'Unregistered', 'last_name': 'User'}
        self.user_info = user_info
        self.root = tk.Tk()
        self.ui = theme.Theme(self.root)

        # Remove the standard title bar and make the window always on top
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)

        self._drag_start_x = None
        self._drag_start_y = None

        self.moved = False
        self.member = station.short_name(user_info.get('first_name'), user_info.get('last_name'))

        self.setup_ui()
        self.place_window()

        self.start_time = time.time()
        self.update_timer()
        self.check_reservations()
        self.root.after(self.refresh_ms(), self.start_refresh)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self):
        """One small row, so it stays out of the way of whatever the member is doing."""
        ui = self.ui
        self.root.configure(bg=theme.BRAND)
        self.warning_label = tk.Label(self.root, bg=theme.WARNING, fg=theme.INK, font=ui.font(11, True),
                                      padx=ui.px(8), pady=ui.px(4), justify="left", wraplength=ui.px(300))
        outer = tk.Frame(self.root, bg=theme.CARD, padx=ui.px(8), pady=ui.px(5))
        outer.pack(side="bottom", fill="both", expand=True, pady=(ui.px(2), 0))

        self.timer_label = tk.Label(outer, text="00:00:00", bg=theme.CARD, fg=theme.INK, font=ui.font(14, True))
        self.timer_label.pack(side=tk.LEFT, padx=(0, ui.px(8)))

        self.end_session_btn = tk.Button(outer, text="End", command=self.end_session, font=ui.font(11, True),
                                         bg=theme.BRAND, fg="#ffffff", activebackground=theme.BRAND_STRONG,
                                         activeforeground="#ffffff", relief="flat", bd=0, highlightthickness=0,
                                         padx=ui.px(9), pady=ui.px(3), cursor="hand2")
        self.end_session_btn.pack(side=tk.RIGHT)

        self.report_btn = tk.Button(outer, text="Report", command=self.open_report, font=ui.font(11, True),
                                    bg=theme.QUIET, fg=theme.INK, activebackground=theme.QUIET_STRONG,
                                    activeforeground=theme.INK, relief="flat", bd=0, highlightthickness=0,
                                    padx=ui.px(9), pady=ui.px(3), cursor="hand2")
        self.report_btn.pack(side=tk.RIGHT, padx=(0, ui.px(5)))
        self.popup = None

        # A station with no tool has no tool page to ask about.
        self.equipment = (station.load_saved_config() or {}).get("equipment") or []
        if any(item.get("url") for item in self.equipment):
            self.ask_btn = tk.Button(outer, text="Ask", command=self.open_help, font=ui.font(11, True),
                                     bg=theme.QUIET, fg=theme.INK, activebackground=theme.QUIET_STRONG,
                                     activeforeground=theme.INK, relief="flat", bd=0, highlightthickness=0,
                                     padx=ui.px(9), pady=ui.px(3), cursor="hand2")
            self.ask_btn.pack(side=tk.RIGHT, padx=(0, ui.px(5)))

        # Make the window draggable, so it can be moved off whatever it covers
        for element in (self.root, outer, self.timer_label):
            element.bind("<Button-1>", self.start_move)
            element.bind("<ButtonRelease-1>", self.stop_move)
            element.bind("<B1-Motion>", self.do_move)

    def place_window(self):
        """Bottom center, until the member drags it somewhere else.

        The website's chat opens in the bottom right corner, and the Windows
        taskbar runs along the bottom edge, so this stays clear of both.
        """
        self.root.update_idletasks()
        width = self.root.winfo_reqwidth()
        height = self.root.winfo_reqheight()
        if self.moved:
            self.root.geometry(f"{width}x{height}")
        else:
            x = (self.root.winfo_screenwidth() - width) // 2
            y = self.root.winfo_screenheight() - height - self.ui.px(56)
            self.root.geometry(f"{width}x{height}+{x}+{y}")

    def refresh_ms(self):
        seconds = (station.load_saved_config() or {}).get("refresh_seconds") or DEFAULT_REFRESH_SECONDS
        return int(seconds) * 1000

    def start_refresh(self):
        """A long session should still hear about a reservation made during it."""
        threading.Thread(target=self.refresh_config, daemon=True).start()
        self.root.after(self.refresh_ms(), self.start_refresh)

    @staticmethod
    def refresh_config():
        # Saves to disk, which check_reservations reads. Never touches the screen.
        if station.fetch_config(station.load_key())[0] == station.OK:
            station.send_pending_reports()

    def check_reservations(self):
        warning = station.reservation_warning(station.load_saved_config(), station.SESSION_WARNING_MINUTES,
                                              member=self.member)
        if warning != self.warning_label.cget("text") or (warning and not self.warning_label.winfo_ismapped()):
            self.warning_label.config(text=warning or "")
            if warning:
                self.warning_label.pack(side="top", fill="x")
            else:
                self.warning_label.pack_forget()
            self.place_window()
        self.root.after(WARNING_CHECK_MS, self.check_reservations)

    def open_popup(self, title):
        """A normal window, because this timer bypasses the window manager and
        so can't take keyboard input. One at a time."""
        if self.popup is not None and self.popup.winfo_exists():
            self.popup.destroy()
        ui = self.ui
        window = tk.Toplevel(self.root, bg=theme.CARD, padx=ui.px(24), pady=ui.px(20))
        window.title(title)
        window.attributes("-topmost", True)
        self.popup = window
        return window

    def center_popup(self):
        window = self.popup
        window.update_idletasks()
        x = (window.winfo_screenwidth() - window.winfo_reqwidth()) // 2
        y = (window.winfo_screenheight() - window.winfo_reqheight()) // 2
        window.geometry(f"+{x}+{y}")
        window.lift()

    def open_report(self):
        window = self.open_popup("Report a problem")
        form = report_form.ReportForm(window, self.ui, station.load_saved_config(), self.user_info, window.destroy)
        form.pack(fill="both", expand=True)
        self.center_popup()
        form.description.focus_force()

    def open_help(self):
        window = self.open_popup("Ask about this tool")
        help_panel.HelpPanel(window, self.ui, self.equipment, window.destroy, self.note_browser_used).pack(
            fill="both", expand=True)
        self.center_popup()

    def note_browser_used(self):
        self.user_info["opened_website"] = True

    def on_closing(self):
        pass

    def update_timer(self):
        elapsed_time = time.time() - self.start_time
        self.timer_label.config(text=time.strftime("%H:%M:%S", time.gmtime(elapsed_time)))
        self.after_id = self.root.after(1000, self.update_timer)

    def end_session(self):
        if hasattr(self, 'after_id'):
            self.root.after_cancel(self.after_id)

        duration = str(datetime.timedelta(seconds=int(time.time() - self.start_time)))
        station.log_event("end", self.user_info, duration=duration)
        station_browser.close_session()  # Before the next screen, so no login outlasts the session.

        script_dir = os.path.dirname(os.path.abspath(__file__))
        display = (station.load_saved_config() or {}).get("display") or {}
        if display.get("show_ending_screen", True):
            user_info_path = station.state_path("temp_user_data.json")
            with open(user_info_path, 'w', encoding="utf-8") as file:
                json.dump(self.user_info, file)
            subprocess.Popen([sys.executable, os.path.join(script_dir, "ending_window.py"), user_info_path])
        else:
            subprocess.Popen([sys.executable, os.path.join(script_dir, "maker-light-auth.pyw")])

        self.root.destroy()  # Close the timer window

    def start_move(self, event):
        self._drag_start_x = event.x_root - self.root.winfo_x()
        self._drag_start_y = event.y_root - self.root.winfo_y()

    def stop_move(self, event):
        self._drag_start_x = None
        self._drag_start_y = None

    def do_move(self, event):
        if self._drag_start_x is not None and self._drag_start_y is not None:
            self.moved = True
            x = event.x_root - self._drag_start_x
            y = event.y_root - self._drag_start_y
            self.root.geometry(f"+{x}+{y}")

    def run(self):
        self.root.mainloop()
