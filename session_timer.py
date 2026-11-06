import datetime
import json
import os
import subprocess
import sys
import time
import tkinter as tk

import report_form
import station
import theme


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

        self.setup_ui()
        self.root.update_idletasks()

        # Position the window in the bottom right corner of the screen
        margin = self.ui.px(8)
        width = self.root.winfo_reqwidth()
        height = self.root.winfo_reqheight()
        x = self.root.winfo_screenwidth() - width - margin
        y = self.root.winfo_screenheight() - height - margin
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        self.start_time = time.time()
        self.update_timer()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self):
        """One small row, so it stays out of the way of whatever the member is doing."""
        ui = self.ui
        self.root.configure(bg=theme.BRAND)
        outer = tk.Frame(self.root, bg=theme.CARD, padx=ui.px(8), pady=ui.px(5))
        outer.pack(fill="both", expand=True, pady=(ui.px(2), 0))

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
        self.report_window = None

        # Make the window draggable, so it can be moved off whatever it covers
        for element in (self.root, outer, self.timer_label):
            element.bind("<Button-1>", self.start_move)
            element.bind("<ButtonRelease-1>", self.stop_move)
            element.bind("<B1-Motion>", self.do_move)

    def open_report(self):
        """A normal window, because this timer bypasses the window manager and
        so can't take keyboard input for a description."""
        if self.report_window is not None and self.report_window.winfo_exists():
            self.report_window.lift()
            return
        ui = self.ui
        window = tk.Toplevel(self.root, bg=theme.CARD, padx=ui.px(24), pady=ui.px(20))
        window.title("Report a problem")
        window.attributes("-topmost", True)
        self.report_window = window
        form = report_form.ReportForm(window, ui, station.load_saved_config(), self.user_info, window.destroy)
        form.pack(fill="both", expand=True)
        window.update_idletasks()
        x = (window.winfo_screenwidth() - window.winfo_reqwidth()) // 2
        y = (window.winfo_screenheight() - window.winfo_reqheight()) // 2
        window.geometry(f"+{x}+{y}")
        window.lift()
        form.description.focus_force()

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
            x = event.x_root - self._drag_start_x
            y = event.y_root - self._drag_start_y
            self.root.geometry(f"+{x}+{y}")

    def run(self):
        self.root.mainloop()
