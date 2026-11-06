"""The "report a problem" form, used from the session timer and the ending screen.

Which problems it offers comes from the station: one that runs a tool asks about
the tool and also its computer, and one with no tool asks about the computer and
its software. A software problem never marks the tool it controls as broken.
"""
import tkinter as tk

import station
import theme


class ReportForm(tk.Frame):
    def __init__(self, parent, ui, config, user_info, on_close):
        super().__init__(parent, bg=theme.CARD)
        self.ui = ui
        self.config_data = config or {}
        self.user_info = user_info or {}
        self.on_close = on_close
        self.equipment = self.config_data.get("equipment") or []
        self.issue = tk.StringVar(self, "")
        self.tool = tk.StringVar(self, str(self.equipment[0].get("id", "")) if self.equipment else "")
        self.build()

    def label(self, parent, text, size=16, bold=False, color=theme.INK):
        return tk.Label(parent, text=text, bg=theme.CARD, fg=color, font=self.ui.font(size, bold),
                        anchor="w", justify="left", wraplength=self.ui.px(560))

    def choice(self, parent, text, variable, value):
        return tk.Radiobutton(parent, text=text, variable=variable, value=value, indicatoron=False, anchor="w",
                              bg=theme.PAGE, fg=theme.INK, selectcolor=theme.GOLD, activebackground=theme.QUIET_STRONG,
                              font=self.ui.font(15), relief="flat", bd=0, highlightthickness=0,
                              padx=self.ui.px(14), pady=self.ui.px(7), cursor="hand2", command=self.update_tools)

    def build(self):
        ui = self.ui
        self.label(self, "Report a problem", 22, True).pack(fill="x")
        self.label(self, "What did you notice? Staff will see this.", 15, color=theme.MUTED).pack(
            fill="x", pady=(ui.px(2), ui.px(12)))

        for value, text in station.issue_choices(self.config_data):
            self.choice(self, text, self.issue, value).pack(fill="x", pady=(0, ui.px(5)))

        # Only a station that runs several tools needs to ask which one.
        self.tools = tk.Frame(self, bg=theme.CARD)
        if len(self.equipment) > 1:
            self.label(self.tools, "Which tool?", 15, True).pack(fill="x", pady=(ui.px(6), ui.px(4)))
            for item in self.equipment:
                self.choice(self.tools, item.get("title", "Tool"), self.tool, str(item.get("id", ""))).pack(
                    fill="x", pady=(0, ui.px(5)))

        self.description_label = self.label(self, "What's wrong?", 15, True)
        self.description_label.pack(fill="x", pady=(ui.px(10), ui.px(4)))
        self.description = tk.Text(self, height=3, width=44, font=ui.font(15), relief="flat", wrap="word",
                                   highlightthickness=ui.px(2), highlightbackground=theme.BORDER,
                                   highlightcolor=theme.BRAND, insertbackground=theme.BRAND,
                                   padx=ui.px(10), pady=ui.px(8))
        self.description.pack(fill="x")

        self.error = self.label(self, "", 14, True, theme.DANGER)
        self.error.pack(fill="x", pady=(ui.px(6), ui.px(6)))

        buttons = tk.Frame(self, bg=theme.CARD)
        buttons.pack(anchor="e")
        ui.button(buttons, "Cancel", self.on_close, "quiet", size=15).pack(side=tk.LEFT, padx=(0, ui.px(10)))
        ui.button(buttons, "Send report", self.send, size=15).pack(side=tk.LEFT)

    def update_tools(self):
        if len(self.equipment) > 1 and station.is_tool_issue(self.issue.get()):
            self.tools.pack(fill="x", before=self.description_label)
        else:
            self.tools.pack_forget()
        self.description.focus_force()

    def send(self):
        issue = self.issue.get()
        text = self.description.get("1.0", "end-1c").strip()
        if not issue:
            self.error.config(text="Please choose what kind of problem it is.")
            return
        if not text:
            self.error.config(text="Please say a little about what's wrong.")
            return
        report = {"issue_type": issue, "description": text}
        if station.is_tool_issue(issue) and self.tool.get():
            report["equipment_id"] = self.tool.get()
        if self.user_info.get("uuid"):
            report["member_uuid"] = self.user_info["uuid"]

        self.error.config(text="Sending...", fg=theme.MUTED)
        self.update()
        outcome, reason = station.submit_report(report)
        if outcome == station.REPORT_REJECTED:
            self.error.config(text=reason or "That report couldn't be sent. Please tell staff.", fg=theme.DANGER)
            return
        self.show_thanks(outcome)

    def show_thanks(self, outcome):
        for widget in self.winfo_children():
            widget.destroy()
        ui = self.ui
        self.label(self, "Thanks for reporting this", 22, True).pack(fill="x")
        message = ("Staff have been told." if outcome == station.REPORT_SENT
                   else "The website isn't answering, so it's saved here and will be sent when it's back. "
                        "If anyone could get hurt, please tell staff now.")
        self.label(self, message, 16, color=theme.MUTED).pack(fill="x", pady=(ui.px(6), ui.px(16)))
        ui.button(self, "Close", self.on_close, "quiet", size=15).pack(anchor="e")
