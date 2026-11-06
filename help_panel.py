"""The timer's "Ask" window: the way to this tool's chat, manuals and page.

The chat needs a MakeHaven login. Scanning the code uses the member's own phone.
On this computer it opens in a throwaway browser, which forgets the login when
the session ends. See station_browser.
"""
import tkinter as tk

import station
import station_browser
import theme


class HelpPanel(tk.Frame):
    def __init__(self, parent, ui, equipment, on_close, on_browser=None):
        super().__init__(parent, bg=theme.CARD)
        self.ui = ui
        self.equipment = [item for item in equipment if item.get("url")]
        self.on_close = on_close
        self.on_browser = on_browser
        self.build()
        self.show_tool(self.equipment[0])

    def label(self, parent, text, size=15, bold=False, color=theme.INK):
        return tk.Label(parent, text=text, bg=theme.CARD, fg=color, font=self.ui.font(size, bold),
                        justify="center", wraplength=self.ui.px(440))

    def build(self):
        ui = self.ui
        self.title = self.label(self, "", 22, True)
        self.title.pack()
        self.label(self, "Scan with your phone to chat with the Tool Guide, or open the chat here.",
                   15, color=theme.MUTED).pack(pady=(ui.px(4), ui.px(12)))

        # Only a station that runs several tools needs to ask which one.
        if len(self.equipment) > 1:
            tools = tk.Frame(self, bg=theme.CARD)
            tools.pack(pady=(0, ui.px(10)))
            for item in self.equipment:
                ui.button(tools, item.get("title", "Tool"), lambda item=item: self.show_tool(item), "quiet",
                          size=13).pack(side=tk.LEFT, padx=ui.px(4))

        self.code = tk.Label(self, bg=theme.CARD)
        self.code.pack()
        self.label(self, "You'll log in to MakeHaven first. On this computer, the login is erased when you end your session.",
                   13, color=theme.MUTED).pack(pady=(ui.px(10), ui.px(14)))

        buttons = tk.Frame(self, bg=theme.CARD)
        buttons.pack()
        ui.button(buttons, "Chat here", lambda: self.open_in_browser(station.chat_url(self.item), bare_window=True),
                  size=14).pack(side=tk.LEFT)
        ui.button(buttons, "Tool page", lambda: self.open_in_browser(self.item["url"]), "quiet",
                  size=14).pack(side=tk.LEFT, padx=ui.px(10))
        ui.button(buttons, "Close", self.on_close, "quiet", size=14).pack(side=tk.LEFT)

    def show_tool(self, item):
        self.item = item
        self.title.config(text=item.get("title", "This tool"))
        photo = self.ui.qr_photo(station.chat_url(item), 220)
        self.code.config(image=photo)
        self.code.image = photo

    def open_in_browser(self, url, bare_window=False):
        if not station_browser.open_page(url, bare_window) and self.on_browser:
            self.on_browser()  # No throwaway browser here, so the login could stay behind.
        self.on_close()  # It would otherwise sit on top of the page it just opened.
