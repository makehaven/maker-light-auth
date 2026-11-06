"""The screen after a session: end message, rating, materials to pay for, reset.

It works from the config saved on this computer and needs no network, so a
website outage can't stop the station getting back to its login prompt. If
anything does go wrong here, the login prompt comes back anyway.

Popups are panels inside this window, not separate windows, so a window manager
can't open one hidden behind this full-screen window.
"""
import io
import json
import os
import subprocess
import sys
import tkinter as tk
import traceback

import qrcode
import requests
from PIL import Image, ImageTk

import report_form
import station
import theme

EXPERIENCE_QUESTION = "How was your experience this session?"
LOW_LABEL = "Poor"
HIGH_LABEL = "Excellent"
DEFAULT_END_MESSAGE = "Remember to clean up and turn off the lights."
RATING_COLORS = ["#dc3545", "#ef8a62", "#ffc658", "#8fce9b", "#1f8c5b"]  # Red to green
RATING_TEXT = ["#ffffff", theme.INK, theme.INK, theme.INK, "#ffffff"]
IMAGE_TIMEOUT = 3


def restart_authentication():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    subprocess.Popen([sys.executable, os.path.join(script_dir, "maker-light-auth.pyw")])


class EndingScreen:
    def __init__(self, user_info, config):
        self.user_info = user_info
        self.station_config = config
        self.pending_rating = None
        self.panel = None
        self.rating_buttons = []
        display = config.get("display") or {}
        details = config.get("station") or {}

        self.root = tk.Tk()
        self.root.title("Session Ended")
        # Same as the login screen. Bypassing the window manager with
        # overrideredirect also loses the keyboard, so comments can't be typed.
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        self.ui = theme.Theme(self.root)
        ui = self.ui

        ui.header(self.root, " · ".join(part for part in (details.get("name"), details.get("area")) if part))

        body = tk.Frame(self.root, bg=theme.PAGE)
        body.pack(fill="both", expand=True, padx=ui.px(40), pady=ui.px(24))

        tk.Label(body, text="Session complete", bg=theme.PAGE, fg=theme.INK, font=ui.font(30, True), anchor="w").pack(fill="x")
        end_message = display.get("end_message") or DEFAULT_END_MESSAGE
        tk.Label(body, text=end_message, bg=theme.PAGE, fg=theme.MUTED, font=ui.font(18), anchor="w",
                 justify="left", wraplength=ui.px(1100)).pack(fill="x", pady=(ui.px(4), ui.px(20)))

        columns = tk.Frame(body, bg=theme.PAGE)
        columns.pack(fill="x")
        materials = config.get("materials") or []
        ask_rating = display.get("ask_rating", True)
        cards = 0
        if ask_rating:
            self.build_rating(columns).grid(row=0, column=cards, sticky="nsew", padx=(0, ui.px(20) if materials else 0))
            columns.grid_columnconfigure(cards, weight=1, uniform="cards")
            cards += 1
        if materials:
            self.build_materials(columns, materials).grid(row=0, column=cards, sticky="nsew")
            columns.grid_columnconfigure(cards, weight=1, uniform="cards")
            cards += 1
        columns.grid_rowconfigure(0, weight=1)

        self.build_reset(body)

    def section_title(self, parent, text):
        tk.Label(parent, text=text, bg=theme.CARD, fg=theme.INK, font=self.ui.font(19, True), anchor="w",
                 justify="left", wraplength=self.ui.px(520)).pack(fill="x", pady=(0, self.ui.px(16)))

    def build_rating(self, parent):
        ui = self.ui
        card = ui.card(parent)
        self.section_title(card, EXPERIENCE_QUESTION)
        row = tk.Frame(card, bg=theme.CARD)
        row.pack(anchor="w")
        for score, color in enumerate(RATING_COLORS, start=1):
            button = tk.Button(row, text=str(score), bg=color, fg=RATING_TEXT[score - 1], activebackground=color,
                               activeforeground=RATING_TEXT[score - 1], disabledforeground=theme.FAINT,
                               font=ui.font(22, True), width=3, relief="flat", bd=0, highlightthickness=0,
                               pady=ui.px(10), cursor="hand2", command=lambda score=score: self.rate(score))
            button.pack(side=tk.LEFT, padx=(0, ui.px(8)))
            self.rating_buttons.append(button)
        labels = tk.Frame(card, bg=theme.CARD)
        labels.pack(fill="x", pady=(ui.px(8), 0))
        tk.Label(labels, text=f"1 = {LOW_LABEL}", bg=theme.CARD, fg=theme.MUTED, font=ui.font(14)).pack(side=tk.LEFT)
        tk.Label(labels, text=f"5 = {HIGH_LABEL}", bg=theme.CARD, fg=theme.MUTED, font=ui.font(14)).pack(side=tk.LEFT, padx=(ui.px(20), 0))
        return card

    def build_materials(self, parent, materials):
        ui = self.ui
        card = ui.card(parent)
        self.section_title(card, "Did you use any materials?")
        for material in materials[:6]:
            row = tk.Button(card, text=self.material_label(material), anchor="w", bg=theme.PAGE, fg=theme.INK,
                            activebackground=theme.QUIET_STRONG, activeforeground=theme.INK, font=ui.font(16),
                            relief="flat", bd=0, highlightthickness=0, padx=ui.px(14), pady=ui.px(9), cursor="hand2",
                            command=lambda material=material: self.show_material(material))
            row.pack(fill="x", pady=(0, ui.px(8)))
        return card

    @staticmethod
    def material_label(material):
        return f"{material.get('label', 'Material')}  ·  ${material.get('cost', '')} per {material.get('unit', 'unit')}"

    def build_reset(self, parent):
        ui = self.ui
        row = tk.Frame(parent, bg=theme.PAGE)
        row.pack(fill="x", pady=(ui.px(28), 0))
        ui.button(row, "Report a problem", self.show_report, "quiet").pack(side=tk.LEFT)
        ui.button(row, "I paid", lambda: self.finish("payment_submitted"), "success").pack(side=tk.RIGHT)
        ui.button(row, "Nothing due", lambda: self.finish("nothing_due")).pack(side=tk.RIGHT, padx=(0, ui.px(12)))
        # Less prominent button for "left open by someone else"
        ui.button(row, "Not me", lambda: self.finish("not_me"), "quiet").pack(side=tk.RIGHT, padx=(0, ui.px(12)))

    def open_panel(self):
        self.close_panel()
        ui = self.ui
        self.panel = tk.Frame(self.root, bg=theme.CARD, highlightthickness=ui.px(3), highlightbackground=theme.BRAND,
                              highlightcolor=theme.BRAND, padx=ui.px(32), pady=ui.px(24))
        self.panel.place(relx=0.5, rely=0.5, anchor="center")
        return self.panel

    def close_panel(self):
        if self.panel is not None:
            self.panel.destroy()
            self.panel = None

    def show_report(self):
        panel = self.open_panel()
        form = report_form.ReportForm(panel, self.ui, self.station_config, self.user_info, self.close_panel)
        form.pack()
        form.description.focus_force()

    def rate(self, score):
        ui = self.ui
        self.pending_rating = score
        for button in self.rating_buttons:
            button.config(state=tk.DISABLED)
        panel = self.open_panel()
        tk.Label(panel, text=f"You rated this session {score} out of 5", bg=theme.CARD, fg=theme.INK,
                 font=ui.font(22, True)).pack(anchor="w")
        tk.Label(panel, text="Anything you'd like to add? (optional)", bg=theme.CARD, fg=theme.MUTED,
                 font=ui.font(16)).pack(anchor="w", pady=(ui.px(4), ui.px(14)))
        comments = tk.Text(panel, height=4, width=44, font=ui.font(16), relief="flat", wrap="word",
                           highlightthickness=ui.px(2), highlightbackground=theme.BORDER, highlightcolor=theme.BRAND,
                           insertbackground=theme.BRAND, padx=ui.px(10), pady=ui.px(8))
        comments.pack(pady=(0, ui.px(18)))
        buttons = tk.Frame(panel, bg=theme.CARD)
        buttons.pack(anchor="e")
        # A rating alone is enough, so leaving without a comment is one click.
        ui.button(buttons, "Skip", lambda: self.submit_rating(""), "quiet").pack(side=tk.LEFT, padx=(0, ui.px(10)))
        ui.button(buttons, "Submit", lambda: self.submit_rating(comments.get("1.0", "end-1c"))).pack(side=tk.LEFT)
        comments.focus_force()

    def submit_rating(self, comments):
        self.record_rating(comments)
        self.close_panel()

    def record_rating(self, comments=""):
        """A chosen rating counts even if the member leaves without pressing Submit."""
        if self.pending_rating is not None:
            station.log_event("rating", self.user_info, rating=self.pending_rating, details=comments)
            self.pending_rating = None

    def show_material(self, material):
        ui = self.ui
        panel = self.open_panel()
        tk.Label(panel, text=material.get("label", "Material"), bg=theme.CARD, fg=theme.INK,
                 font=ui.font(24, True)).pack()
        tk.Label(panel, text=f"${material.get('cost', '')} per {material.get('unit', 'unit')}", bg=theme.CARD,
                 fg=theme.MUTED, font=ui.font(17)).pack(pady=(ui.px(2), ui.px(12)))
        self.add_material_image(panel, material.get("image"))
        self.add_payment_code(panel, material.get("purchase"))
        ui.button(panel, "Close", self.close_panel, "quiet").pack(pady=(ui.px(14), 0))

    def add_material_image(self, panel, url):
        """A photo is a nicety: with no network the panel just goes without one."""
        if not url:
            return
        try:
            response = requests.get(url, timeout=IMAGE_TIMEOUT)
            response.raise_for_status()
            image = Image.open(io.BytesIO(response.content))
            height = self.ui.px(90)
            width = max(1, int(image.size[0] * height / image.size[1]))
            photo = ImageTk.PhotoImage(image.resize((width, height), Image.LANCZOS), master=self.root)
        except Exception as error:
            print(f"Failed to load image: {error}")
            return
        label = tk.Label(panel, image=photo, bg=theme.CARD)
        label.image = photo
        label.pack(pady=(0, self.ui.px(10)))

    def add_payment_code(self, panel, url):
        ui = self.ui
        if not url:
            tk.Label(panel, text="Online payment isn't set up for this item.\nPlease ask staff.", bg=theme.CARD,
                     fg=theme.INK, font=ui.font(16)).pack(pady=ui.px(6))
            return
        tk.Label(panel, text="Scan with your phone to pay", bg=theme.CARD, fg=theme.INK, font=ui.font(16, True)).pack()
        code = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=2)
        code.add_data(url)
        code.make(fit=True)
        size = ui.px(190)
        image = code.make_image(fill_color="black", back_color="white").convert("RGB")
        photo = ImageTk.PhotoImage(image.resize((size, size), Image.NEAREST), master=self.root)
        label = tk.Label(panel, image=photo, bg=theme.CARD)
        label.image = photo
        label.pack(pady=(ui.px(6), 0))

    def finish(self, action):
        self.record_rating()
        station.log_event(action, self.user_info)
        restart_authentication()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def read_user_info():
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1], encoding="utf-8") as handle:
                user_info = json.load(handle)
            os.remove(sys.argv[1])  # Clean up the temporary file
            return user_info
        except (OSError, ValueError) as error:
            print(f"Could not read the session's user info: {error}")
    return {'first_name': 'Unknown', 'last_name': 'Unknown'}


if __name__ == "__main__":
    try:
        EndingScreen(read_user_info(), station.load_saved_config() or {}).run()
    except Exception:
        traceback.print_exc()
        restart_authentication()
