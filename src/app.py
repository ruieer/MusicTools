"""Music Tools - окно приложения (CustomTkinter).

Запуск из исходников:  python app.py
"""
import queue
import re
from tkinter import TclError, ttk

from core import env

env.setup()   # пути и PATH для ffmpeg - до импорта движка

import customtkinter as ctk  # noqa: E402

from core import engine, settings, tools  # noqa: E402
from core.runner import Runner  # noqa: E402
from ui.pages import PAGES  # noqa: E402
from ui import theme as T  # noqa: E402

PROGRESS_RE = re.compile(r"\[(\d+)/(\d+)\]")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        T.set_accent(settings.load().get("accent_color"))
        T.apply(ctk)
        self.title("Music Tools")
        self.configure(fg_color=T.BG)
        self.geometry("1120x780")
        self.minsize(980, 680)

        self.cfg = settings.load()
        self.runner = Runner()          # подменяет input() и sys.stdout - до запуска любых задач
        self.run_buttons = []
        self._job_running = False
        self._job_title = ""
        self._quick = lambda _prompt: []

        self._build()
        self.show("download")
        self.after(60, self._pump)
        self.after(120, self._check_tools)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    # --- разметка -----------------------------------------------------------

    def _build(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        side = ctk.CTkFrame(self, width=230, corner_radius=0, fg_color=T.SIDEBAR)
        side.grid(row=0, column=0, sticky="nsw")
        side.grid_propagate(False)
        ctk.CTkLabel(side, text="Music Tools", font=ctk.CTkFont(size=22, weight="bold")
                     ).pack(anchor="w", padx=20, pady=(24, 0))
        ctk.CTkLabel(side, text="музыка для iPod", text_color=T.MUTED).pack(anchor="w", padx=20, pady=(0, 18))
        self._nav = {}
        self._nav_active = None
        for key, title, _cls in PAGES:
            # иконка в отдельной колонке фиксированной ширины: у ▣, ◐, ⚙ разная ширина
            # в шрифте, и в общей строке подписи вставали бы со сдвигом
            row = ctk.CTkFrame(side, height=40, corner_radius=10, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=2)
            row.pack_propagate(False)
            icon = ctk.CTkLabel(row, text=T.ICONS.get(key, "•"), width=26, anchor="center",
                                text_color=T.TEXT, font=ctk.CTkFont(size=14))
            icon.pack(side="left", padx=(11, 4))
            ctk.CTkLabel(row, text=title, anchor="w", text_color=T.TEXT,
                         font=ctk.CTkFont(size=14)).pack(side="left", fill="x", expand=True)
            for widget in row.winfo_children() + [row]:
                widget.bind("<Button-1>", lambda _e, k=key: self.show(k))
                widget.bind("<Enter>", lambda _e, k=key: self._nav_hover(k, True))
                widget.bind("<Leave>", lambda _e, k=key: self._nav_hover(k, False))
            self._nav[key] = row

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=18, pady=18)
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        # страницы инструментов лежат друг на друге, показываем нужную через tkraise()
        self.host = ctk.CTkFrame(main, height=300, fg_color=T.CARD, corner_radius=14,
                                 border_width=1, border_color=T.CARD_BORDER)
        self.host.grid(row=0, column=0, sticky="ew")
        self.host.grid_propagate(False)
        self.host.grid_columnconfigure(0, weight=1)
        self.host.grid_rowconfigure(0, weight=1)
        self.pages = {}
        for key, _title, cls in PAGES:
            page = cls(self.host, self)
            page.grid(row=0, column=0, sticky="nsew", padx=14, pady=12)
            self.pages[key] = page

        self.log = ctk.CTkTextbox(main, font=ctk.CTkFont(family="Consolas", size=12), wrap="word",
                                  fg_color=T.CARD, corner_radius=14, border_width=1,
                                  border_color=T.CARD_BORDER, text_color=T.TEXT)
        self.log.grid(row=1, column=0, sticky="nsew", pady=(14, 8))
        self.log.configure(state="disabled")

        bar = ctk.CTkFrame(main, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew")
        bar.grid_columnconfigure(1, weight=1)
        self.stop_btn = ctk.CTkButton(bar, text="Остановить", width=120, fg_color=T.DANGER,
                                      hover_color=T.DANGER_HOVER, text_color="#ffffff",
                                      state="disabled", command=self._stop)
        self.stop_btn.grid(row=0, column=0, padx=(0, 10))
        self.progress = ctk.CTkProgressBar(bar, progress_color=T.ACCENT, fg_color=T.CARD_BORDER)
        self.progress.grid(row=0, column=1, sticky="ew")
        self.progress.set(0)
        self.status = ctk.CTkLabel(bar, text="Готово к работе", width=300, anchor="e")
        self.status.grid(row=0, column=2, padx=(12, 0))
        ctk.CTkButton(bar, text="Очистить лог", width=110, fg_color=T.BUTTON_SOFT,
                      hover_color=T.BUTTON_SOFT_HOVER, text_color=T.SOFT_TEXT,
                      command=self._clear_log).grid(row=0, column=3, padx=(12, 0))

        # строка ответа: сюда приходят вопросы движка, которые не заполнены на форме
        self.prompt_box = ctk.CTkFrame(main, corner_radius=14, fg_color=T.CARD, border_width=1,
                                       border_color=T.CARD_BORDER)
        self.prompt_box.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.prompt_box.grid_columnconfigure(0, weight=1)
        self.prompt_label = ctk.CTkLabel(self.prompt_box, text="Вопросов нет", anchor="w", text_color="gray60")
        self.prompt_label.grid(row=0, column=0, columnspan=2, sticky="ew", padx=14, pady=(10, 4))
        self.entry = ctk.CTkEntry(self.prompt_box, placeholder_text="Ответ и Enter", state="disabled")
        self.entry.grid(row=1, column=0, sticky="ew", padx=(14, 8))
        self.entry.bind("<Return>", lambda e: self._send())
        self.send_btn = ctk.CTkButton(self.prompt_box, text="Отправить", width=110, state="disabled",
                                      fg_color=T.BUTTON_SOFT, hover_color=T.BUTTON_SOFT_HOVER,
                                      text_color=T.SOFT_TEXT, command=self._send)
        self.send_btn.grid(row=1, column=1, padx=(0, 14))
        self.quick_row = ctk.CTkFrame(self.prompt_box, fg_color="transparent", height=34)
        self.quick_row.grid(row=2, column=0, columnspan=2, sticky="w", padx=14, pady=(8, 10))
        self.quick_row.grid_propagate(False)

    # --- навигация и задачи -------------------------------------------------

    def show(self, key):
        page = self.pages[key]
        self.host.configure(height=getattr(page, "host_height", 300))
        page.refresh()
        page.tkraise()
        self._nav_active = key
        for k, row in self._nav.items():
            row.configure(fg_color=T.NAV_ACTIVE if k == key else "transparent")

    def _nav_hover(self, key, inside):
        if key == self._nav_active:
            return
        self._nav[key].configure(fg_color=T.NAV_HOVER if inside else "transparent")

    def apply_accent(self, color):
        names = (
            "BG", "SIDEBAR", "CARD", "CARD_BORDER", "ACCENT", "ACCENT_HOVER",
            "NAV_ACTIVE", "NAV_HOVER", "SCROLL_HOVER", "OPTION_HOVER", "BUTTON_TEXT",
            "BUTTON_SOFT", "BUTTON_SOFT_HOVER", "TEXT_DISABLED",
        )
        old = {name: getattr(T, name) for name in names}
        T.set_accent(color)
        T.apply(ctk)
        palette = {old[name]: getattr(T, name) for name in names}
        color_options = (
            "fg_color", "bg_color", "hover_color", "border_color", "button_color",
            "button_hover_color", "selected_color", "selected_hover_color",
            "unselected_color", "unselected_hover_color", "progress_color",
            "label_fg_color", "text_color_disabled",
        )

        pending = [(self, T.BG)]
        while pending:
            widget, parent_bg = pending.pop()
            if getattr(widget, "_accent_swatch", False):
                widget.configure(border_color=T.CARD, bg_color=parent_bg)
                continue
            accent_button = isinstance(widget, (ctk.CTkButton, ctk.CTkOptionMenu))
            if accent_button:
                accent_button = self._has_color(widget, "fg_color", old["ACCENT"])
            self._replace_widget_colors(widget, palette, color_options)
            if self._has_color(widget, "fg_color", "transparent"):
                try:
                    widget.configure(bg_color=parent_bg)
                except (AttributeError, TclError, ValueError):
                    pass
            pending.extend((child, self._widget_background(widget, parent_bg))
                           for child in widget.winfo_children())
            if accent_button:
                self._replace_widget_colors(
                    widget, {old["BUTTON_TEXT"]: T.BUTTON_TEXT}, ("text_color",)
                )

        style = ttk.Style(self)
        style.configure("Lib.Treeview", background=T.BG, fieldbackground=T.BG,
                        foreground=T.TEXT, rowheight=22, borderwidth=0)
        style.configure("Lib.Treeview.Heading", background=T.CARD_BORDER)
        style.configure("Lib.Treeview.Heading", foreground=T.TEXT)
        style.map("Lib.Treeview", background=[("selected", T.NAV_ACTIVE)])
        style.map("Lib.Treeview.Heading", background=[("active", T.NAV_HOVER)])

    @staticmethod
    def _has_color(widget, option, color):
        try:
            current = widget.cget(option)
        except (AttributeError, TclError, ValueError):
            return False
        return current == color or isinstance(current, (tuple, list)) and color in current

    @staticmethod
    def _widget_background(widget, fallback):
        try:
            color = widget.cget("fg_color")
        except (AttributeError, TclError, ValueError):
            return fallback
        if color == "transparent":
            return fallback
        if isinstance(color, (tuple, list)):
            return color[-1] if color else fallback
        return color

    @staticmethod
    def _replace_widget_colors(widget, palette, options):
        updates = {}
        for option in options:
            try:
                current = widget.cget(option)
            except (AttributeError, TclError, ValueError):
                continue
            for previous, updated in palette.items():
                if current == previous or isinstance(current, (tuple, list)) and previous in current:
                    updates[option] = updated
                    break
        if updates:
            widget.configure(**updates)

    def say(self, text):
        self.status.configure(text=text)

    def start_job(self, title, fn, answers=(), quick=()):
        if self._job_running:
            return self.say("Уже выполняется другая задача")
        try:
            engine.apply(self.cfg)
        except OSError as ex:
            return self.say(f"Не могу открыть папку музыки: {ex}")
        self._quick = quick if callable(quick) else (lambda _p, q=list(quick): q)
        self._job_title = title
        self._job_running = True
        self._log(f"\n━━━━ {title} ━━━━\n")
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self.status.configure(text=f"Работает: {title}")
        self._set_busy(True)
        self._hide_prompt()
        self.runner.start(fn, answers=answers)

    def _stop(self):
        self.say("Останавливаю…")
        self.runner.stop()

    # --- приём событий от фонового потока -----------------------------------

    def _pump(self):
        while True:
            try:
                kind, data = self.runner.events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                self._log(data)
                self._progress_from(data)
            elif kind == "ask":
                self._show_prompt(data)
            elif kind == "finish":
                self._finish(data)
        self.after(60, self._pump)

    def _progress_from(self, text):
        found = PROGRESS_RE.findall(text)
        if not found:
            return
        done, total = found[-1]
        total = int(total)
        if total <= 0:
            return
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(min(int(done) / total, 1.0))
        self.status.configure(text=f"{self._job_title}: {done} из {total}")

    def _finish(self, status):
        self._job_running = False
        self._set_busy(False)
        self._hide_prompt()
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(1.0 if status == "done" else 0.0)
        text = {"done": "Готово", "stopped": "Остановлено", "error": "Ошибка - см. лог"}.get(status, status)
        self.status.configure(text=text)
        self._log(f"— {text} —\n")

    # --- строка ответа ------------------------------------------------------

    def _show_prompt(self, prompt):
        self.prompt_label.configure(text=prompt.strip() or "Введите ответ", text_color=("gray10", "gray90"))
        self.entry.configure(state="normal")
        self.entry.delete(0, "end")
        self.send_btn.configure(state="normal", fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER,
                                text_color=T.BUTTON_TEXT)
        self.entry.focus_set()
        for w in self.quick_row.winfo_children():
            w.destroy()
        for label, value in self._quick(prompt):
            ctk.CTkButton(self.quick_row, text=label, height=30, width=140, fg_color=T.BUTTON_SOFT,
                          hover_color=T.BUTTON_SOFT_HOVER, text_color=T.SOFT_TEXT,
                          command=lambda v=value: self._send_value(v)
                          ).pack(side="left", padx=(0, 8))

    def _hide_prompt(self):
        self.entry.delete(0, "end")
        self.entry.configure(state="disabled")
        self.send_btn.configure(state="disabled", fg_color=T.BUTTON_SOFT,
                                hover_color=T.BUTTON_SOFT_HOVER, text_color=T.SOFT_TEXT)
        for w in self.quick_row.winfo_children():
            w.destroy()
        if self._job_running:
            self.prompt_label.configure(text="Задача работает…", text_color="gray60")
        else:
            self.prompt_label.configure(text="Вопросов нет", text_color="gray60")

    def _send(self):
        self._send_value(self.entry.get())

    def _send_value(self, value):
        if not self.runner.waiting:
            return
        self._hide_prompt()
        self.runner.answer(value)

    # --- служебное ----------------------------------------------------------

    def _set_busy(self, busy):
        for b in self.run_buttons:
            b.configure(state="disabled" if busy else "normal")
        self.stop_btn.configure(state="normal" if busy else "disabled")

    def _log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _check_tools(self):
        self._log(tools.report())


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
