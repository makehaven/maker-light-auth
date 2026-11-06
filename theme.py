"""The station's look: MakeHaven's website colors, and sizes that fit any screen.

Colors match the website's tokens.css. Fonts are sized in pixels and scaled to
the screen, so a station looks the same on a small monitor and a very large one.
"""
import os
import subprocess
import tkinter as tk
import tkinter.font as tkfont

from PIL import Image, ImageTk

BRAND = "#8b1919"
BRAND_STRONG = "#710a0a"
GOLD = "#ffc658"
INK = "#1e1f24"
MUTED = "#616161"
FAINT = "#9e9e9e"
PAGE = "#f2f2f2"
CARD = "#ffffff"
BORDER = "#d9d9d9"
SUCCESS = "#1f8c5b"
SUCCESS_STRONG = "#176c46"
DANGER = "#b02a37"
WARNING = "#ffb347"
INFO = "#2f6f9f"
QUIET = "#e7e7e7"
QUIET_STRONG = "#dcdcdc"

# Each status: banner background, banner text.
STATUS = {
    "info": (INFO, "#ffffff"),
    "ok": (SUCCESS, "#ffffff"),
    "bad": (DANGER, "#ffffff"),
    "warn": (WARNING, INK),
}

_BASE_WIDTH = 1280
_BASE_HEIGHT = 800
_FAMILIES = ("Segoe UI", "Inter", "Noto Sans", "Ubuntu", "Helvetica Neue", "Arial", "DejaVu Sans")
_LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.png")


class Theme:
    """Sizes and fonts worked out for one screen."""

    def __init__(self, root):
        self.root = root
        ratio = min(root.winfo_screenwidth() / _BASE_WIDTH, root.winfo_screenheight() / _BASE_HEIGHT)
        self.scale = max(0.8, min(ratio, 4.0))
        self._match_font_dpi()
        available = set(tkfont.families(root))
        self.family = next((name for name in _FAMILIES if name in available), "TkDefaultFont")
        root.configure(bg=PAGE)

    def _match_font_dpi(self):
        """Make a font's pixel size true on Linux desktops with a HiDPI setting.

        Tk turns pixels into points using its own scaling, then the font library
        turns points back into pixels using the desktop's Xft.dpi. If the two
        disagree, all text comes out the wrong size (3x with Xft.dpi 288).
        """
        if self.root.tk.call("tk", "windowingsystem") != "x11":
            return
        try:
            resources = subprocess.run(["xrdb", "-query"], capture_output=True, text=True, timeout=2).stdout
        except (OSError, subprocess.SubprocessError):
            return
        for line in resources.splitlines():
            name, _, value = line.partition(":")
            if name.strip() == "Xft.dpi":
                try:
                    dpi = float(value)
                except ValueError:
                    return
                if dpi > 0:
                    self.root.tk.call("tk", "scaling", dpi / 72)
                return

    def px(self, size):
        return max(1, round(size * self.scale))

    def font(self, size, bold=False):
        # A negative size means pixels, so the OS's DPI setting can't change the layout.
        return (self.family, -self.px(size), "bold" if bold else "normal")

    def card(self, parent, pad=24):
        return tk.Frame(parent, bg=CARD, highlightthickness=max(1, self.px(1)), highlightbackground=BORDER,
                        highlightcolor=BORDER, padx=self.px(pad), pady=self.px(pad))

    def button(self, parent, text, command, kind="primary", size=16):
        colors = {
            "primary": (BRAND, BRAND_STRONG, "#ffffff"),
            "success": (SUCCESS, SUCCESS_STRONG, "#ffffff"),
            "quiet": (QUIET, QUIET_STRONG, INK),
        }[kind]
        return tk.Button(parent, text=text, command=command, font=self.font(size, True), bg=colors[0], fg=colors[2],
                         activebackground=colors[1], activeforeground=colors[2], relief="flat", bd=0,
                         highlightthickness=0, padx=self.px(22), pady=self.px(11), cursor="hand2")

    def header(self, parent, right_text=""):
        """White bar with the logo, a station name, and a brand-red line under it."""
        bar = tk.Frame(parent, bg=CARD, padx=self.px(28), pady=self.px(14))
        bar.pack(fill="x")
        logo = self.logo(bar, 300)
        logo.pack(side="left")
        label = tk.Label(bar, text=right_text, bg=CARD, fg=MUTED, font=self.font(16))
        label.pack(side="right")
        tk.Frame(parent, bg=BRAND, height=self.px(4)).pack(fill="x")
        return label

    def logo(self, parent, width):
        try:
            image = Image.open(_LOGO)
            target = self.px(width)
            image = image.resize((target, max(1, target * image.size[1] // image.size[0])), Image.LANCZOS)
            photo = ImageTk.PhotoImage(image, master=self.root)
        except Exception as error:
            print(f"Could not load the logo: {error}")
            return tk.Label(parent, text="MakeHaven", bg=CARD, fg=BRAND, font=self.font(22, True))
        label = tk.Label(parent, image=photo, bg=CARD, bd=0)
        label.image = photo
        return label
