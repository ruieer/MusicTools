"""Страницы инструментов: каждая - форма и кнопка запуска."""
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

import customtkinter as ctk

from core import engine, settings
from core.env import APP_DIR
from ui import theme as T


# --- кнопки ответов для вопросов движка ------------------------------------
# Значения - ровно то, что ждут скрипты (см. ask() в каждом модуле движка).

def link_quick(prompt):
    if "Ссылка" in prompt:
        return [("Режим: замена", "з"), ("Режим: скачать", "с"), ("Выход", "")]
    if "Имя файла" in prompt:
        return [("По умолчанию", "")]
    return [("Отмена", "")]


def manual_quick(prompt):
    p = prompt.lower()
    if "всё равно" in p:
        return [("Да, оставить", "д"), ("Нет", "")]
    if "скачать?" in p:
        return [("Скачать", "д"), ("Дальше", ""), ("Пропустить", "п"),
                ("Поиск в браузере", "о"), ("Выход", "й")]
    return [("Поиск в браузере", "о"), ("Пропустить навсегда", "п"),
            ("На потом", ""), ("Выход", "й")]


RETAG_QUICK = [("Пропустить", "")]
GAIN_QUICK = [("Да, применить", "д"), ("Отмена", "")]


def _lines(text: str):
    return [l.strip() for l in text.splitlines() if l.strip()]


class Page(ctk.CTkFrame):
    title = ""
    hint = ""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(self, text=self.title, font=ctk.CTkFont(size=22, weight="bold"),
                     anchor="w").grid(row=0, column=0, sticky="ew", padx=4, pady=(2, 0))
        if self.hint:
            ctk.CTkLabel(self, text=self.hint, text_color=T.MUTED, anchor="w", justify="left",
                         wraplength=740).grid(row=1, column=0, sticky="ew", padx=4, pady=(4, 10))
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=2, column=0, sticky="nsew")
        self.body.grid_columnconfigure(0, weight=1)
        self.build()

    def build(self):
        pass

    def refresh(self):
        """Вызывается при показе страницы: обновить то, что зависит от настроек/файлов."""

    def run_button(self, text, command, row):
        b = ctk.CTkButton(self.body, text=text, command=command, width=200, height=36)
        b.grid(row=row, column=0, sticky="w", pady=(10, 0))
        self.app.run_buttons.append(b)
        return b


class DownloadPage(Page):
    title = "Загрузка списка"
    hint = ("Строки в формате «Исполнитель - Название», по одной на строку. Аудио ищется на YouTube "
            "и SoundCloud, теги и обложки - в MusicBrainz, Spotify, Deezer, Bandcamp и Last.fm. "
            "Формат и качество задаются в Настройках. Уже скачанные треки пропускаются.")

    def build(self):
        self.body.grid_rowconfigure(0, weight=1)
        self.box = ctk.CTkTextbox(self.body, height=160)
        self.box.grid(row=0, column=0, sticky="nsew")
        self.box.bind("<KeyRelease>", lambda e: self._count())
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ctk.CTkButton(row, text="Открыть .txt…", width=130, command=self._load).pack(side="left")
        self.count = ctk.CTkLabel(row, text="Треков: 0", text_color="gray60")
        self.count.pack(side="left", padx=14)
        b = ctk.CTkButton(row, text="Запустить загрузку", width=200, height=36, command=self._run)
        b.pack(side="right")
        self.app.run_buttons.append(b)

    def _load(self):
        path = filedialog.askopenfilename(parent=self.app, title="Список треков",
                                          filetypes=[("Текст", "*.txt"), ("Все файлы", "*.*")])
        if path:
            text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
            self.box.delete("1.0", "end")
            self.box.insert("1.0", text)
            self._count()

    def _count(self):
        self.count.configure(text=f"Треков: {len(_lines(self.box.get('1.0', 'end')))}")

    def _run(self):
        lines = _lines(self.box.get("1.0", "end"))
        if not lines:
            return self.app.say("Список пуст - добавьте треки")
        engine.write_list(lines)
        self.app.start_job("Загрузка списка", engine.run_download)


class LinkPage(Page):
    title = "Скачать или заменить по ссылке"
    hint = ("Ссылки вводятся в строку ответа внизу. Режим «скачать» добавляет новый трек, "
            "режим «замена» подменяет уже скачанный - старый файл сохраняется в replaced_backup.")

    def build(self):
        ctk.CTkLabel(self.body, anchor="w", justify="left",
                     text="1. Нажмите «Начать».\n"
                          "2. Вставьте ссылку на YouTube или SoundCloud и нажмите Enter.\n"
                          "3. Чтобы закончить, нажмите «Выход».").grid(row=0, column=0, sticky="w", pady=(4, 0))
        self.run_button("Начать", lambda: self.app.start_job(
            "Скачать по ссылке", engine.run_link, quick=link_quick), row=1)


class ManualPage(Page):
    title = "Ручной разбор ненайденных"
    hint = ("Треки со статусом review, error или missing из report.csv. Для каждого можно выбрать вариант "
            "из поиска, вставить свою ссылку, пропустить или отложить. Ответы - кнопками под строкой ввода.")

    def build(self):
        self.info = ctk.CTkLabel(self.body, anchor="w", justify="left", text="")
        self.info.grid(row=0, column=0, sticky="w", pady=(4, 0))
        self.run_button("Начать разбор", lambda: self.app.start_job(
            "Ручной разбор", engine.run_manual, quick=manual_quick), row=1)

    def refresh(self):
        ok = (APP_DIR / "report.csv").exists()
        self.info.configure(text="Отчёт report.csv найден." if ok else
                            "report.csv не найден: сначала запустите «Загрузка списка».")


class RetagPage(Page):
    title = "Теги для готовых файлов"
    hint = ("Вставьте пути к m4a/mp3, имена «Исполнитель - Название» или путь к .txt-файлу - по одному в строке. "
            "Альбом, год и жанр берутся из источников, ссылки на видео - из журналов скачивания.")

    def build(self):
        self.body.grid_rowconfigure(0, weight=1)
        self.box = ctk.CTkTextbox(self.body, height=150)
        self.box.grid(row=0, column=0, sticky="nsew")
        opts = ctk.CTkFrame(self.body, fg_color="transparent")
        opts.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.cover_var = ctk.BooleanVar(value=False)
        self.manual_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(opts, text="Заменять обложки на найденные", variable=self.cover_var).pack(side="left")
        ctk.CTkCheckBox(opts, text="Вводить вручную, если не нашлось", variable=self.manual_var).pack(side="left", padx=20)
        b = ctk.CTkButton(self.body, text="Запустить", width=200, height=36, command=self._run)
        b.grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.app.run_buttons.append(b)

    def _run(self):
        lines = _lines(self.box.get("1.0", "end"))
        if not lines:
            return self.app.say("Ничего не введено")
        # gather() читает строки до пустой, затем два вопроса: обложки и ручной ввод
        answers = lines + ["", "д" if self.cover_var.get() else "", "д" if self.manual_var.get() else ""]
        self.app.start_job("Теги", engine.run_retag, answers=answers, quick=RETAG_QUICK)


class CoversPage(Page):
    title = "Исправить обложки"
    hint = ("Срезает однотонные полосы по краям обложек уже скачанных треков и приводит их к 500×500. "
            "Интернет не нужен, аудио не меняется.")

    def build(self):
        self.info = ctk.CTkLabel(self.body, anchor="w", justify="left", text="")
        self.info.grid(row=0, column=0, sticky="w", pady=(4, 0))
        self.run_button("Запустить", lambda: self.app.start_job("Обложки", engine.run_covers), row=1)

    def refresh(self):
        self.info.configure(text=f"Папка: {settings.music_dir(self.app.cfg)}")


class GainPage(Page):
    title = "Громкость"
    hint = ("Делает треки тише или громче: -3 - тише, +4 - громче (до ±30 дБ). Каждый файл перекодируется "
            "один раз, оригиналы сохраняются в gain_backup. Не применяйте разные значения к одному файлу подряд.")

    def build(self):
        self.body.grid_rowconfigure(2, weight=1)
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(row, text="Изменение, дБ:").pack(side="left")
        self.db = ctk.CTkEntry(row, width=110)
        self.db.insert(0, "-3")
        self.db.pack(side="left", padx=(8, 0))
        ctk.CTkLabel(self.body, anchor="w", text_color="gray60",
                     text="Что обработать - по одной строке: путь, «Исполнитель - Название» или «все»"
                     ).grid(row=1, column=0, sticky="w", pady=(10, 4))
        self.box = ctk.CTkTextbox(self.body, height=110)
        self.box.grid(row=2, column=0, sticky="nsew")
        b = ctk.CTkButton(self.body, text="Запустить", width=200, height=36, command=self._run)
        b.grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.app.run_buttons.append(b)

    def _run(self):
        lines = _lines(self.box.get("1.0", "end"))
        if not lines:
            return self.app.say("Укажите, что обработать")
        # первый вопрос - дБ, затем список; подтверждение покажется в строке ответа
        answers = [self.db.get().strip()] + lines + [""]
        self.app.start_job("Громкость", engine.run_gain, answers=answers, quick=GAIN_QUICK)


class SettingsPage(Page):
    title = "Настройки"
    host_height = 500

    def build(self):
        self.body.grid_rowconfigure(0, weight=1)
        g = ctk.CTkScrollableFrame(self.body, fg_color="transparent")
        g.grid(row=0, column=0, sticky="nsew")
        g.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(g, text="Папка с музыкой", anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=4)
        self.dir_entry = ctk.CTkEntry(g)
        self.dir_entry.grid(row=0, column=1, sticky="ew")
        ctk.CTkButton(g, text="Выбрать…", width=100, command=self._pick).grid(row=0, column=2, padx=(8, 0))
        ctk.CTkButton(g, text="Открыть", width=100, command=self._open).grid(row=0, column=3, padx=(8, 0))

        ctk.CTkLabel(g, text="Spotify Client ID", anchor="w").grid(row=1, column=0, sticky="w", padx=(0, 12), pady=4)
        self.sid = ctk.CTkEntry(g)
        self.sid.grid(row=1, column=1, columnspan=3, sticky="ew")
        ctk.CTkLabel(g, text="Spotify Client Secret", anchor="w").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=4)
        self.ssec = ctk.CTkEntry(g, show="•")
        self.ssec.grid(row=2, column=1, columnspan=3, sticky="ew")
        ctk.CTkLabel(g, text="Last.fm API key", anchor="w").grid(row=3, column=0, sticky="w", padx=(0, 12), pady=4)
        self.lfm = ctk.CTkEntry(g, show="•", placeholder_text="необязательно")
        self.lfm.grid(row=3, column=1, columnspan=3, sticky="ew")
        ctk.CTkLabel(g, text="Ключи Spotify и Last.fm необязательны: без Spotify работает запасной режим "
                             "(без жанров), без Last.fm жанры берутся из Deezer и MusicBrainz.",
                     text_color=T.MUTED, anchor="w", justify="left", wraplength=700
                     ).grid(row=4, column=1, columnspan=3, sticky="w")

        plate = ctk.CTkFrame(g, fg_color=T.CARD, corner_radius=12)
        plate.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(16, 4))
        inner = ctk.CTkFrame(plate, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=14)
        ctk.CTkLabel(inner, text="Формат и качество", font=ctk.CTkFont(size=15, weight="bold"),
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(inner, text="YouTube обычно отдаёт AAC около 128 кбит/с. 192 и 256 — перекодировка "
                                 "через ffmpeg. MP3 всегда собирается ffmpeg из лучшего доступного аудио.",
                     text_color=T.MUTED, anchor="w", justify="left", wraplength=700).pack(fill="x", pady=(4, 10))
        fmt_row = ctk.CTkFrame(inner, fg_color="transparent")
        fmt_row.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(fmt_row, text="Формат", width=90, anchor="w").pack(side="left")
        self.fmt_var = ctk.StringVar(value="M4A")
        ctk.CTkSegmentedButton(fmt_row, values=["M4A", "MP3"], variable=self.fmt_var,
                               width=220).pack(side="left")
        q_row = ctk.CTkFrame(inner, fg_color="transparent")
        q_row.pack(fill="x")
        ctk.CTkLabel(q_row, text="кбит/с", width=90, anchor="w").pack(side="left")
        self.quality_var = ctk.StringVar(value="128")
        ctk.CTkSegmentedButton(q_row, values=["128", "192", "256"], variable=self.quality_var,
                               width=280).pack(side="left")

        ctk.CTkLabel(g, text="Цвет оформления", anchor="w").grid(row=6, column=0, sticky="w", padx=(0, 12),
                                                                 pady=(12, 4))
        colors = ctk.CTkFrame(g, fg_color="transparent")
        colors.grid(row=6, column=1, columnspan=3, sticky="w", pady=(12, 4))
        self.accent = self.app.cfg.get("accent_color") or T.ACCENT
        for name, color in T.PRESETS:
            swatch = ctk.CTkButton(
                colors, text="", width=30, height=30, corner_radius=15, fg_color=color,
                hover_color=color, border_width=2, border_color=T.CARD,
                command=lambda c=color: self._set_accent(c),
            )
            swatch._accent_swatch = True
            swatch.pack(side="left", padx=(0, 6))
        ctk.CTkButton(colors, text="Свой…", width=80, command=self._pick_accent).pack(side="left", padx=(6, 0))
        self.accent_label = ctk.CTkLabel(colors, text="", width=170, anchor="w")
        self.accent_label.pack(side="left", padx=(12, 0))
        self._set_accent(self.accent)

        actions = ctk.CTkFrame(g, fg_color="transparent")
        actions.grid(row=7, column=1, columnspan=3, sticky="w", pady=(12, 0))
        ctk.CTkButton(actions, text="Сохранить", width=140, height=36, command=self._save).pack(side="left")
        ctk.CTkButton(actions, text="Сохранить и перезапустить", width=210, height=36,
                      command=self._save_restart).pack(side="left", padx=(8, 0))
        ctk.CTkButton(actions, text="Проверить обновления", width=190, height=36,
                      command=self._check_updates).pack(side="left", padx=(8, 0))
        self.info = ctk.CTkLabel(g, text="", anchor="w", justify="left", text_color=T.MUTED)
        self.info.grid(row=8, column=0, columnspan=4, sticky="w", pady=(14, 0))

    def refresh(self):
        cfg = self.app.cfg
        self.dir_entry.delete(0, "end")
        self.dir_entry.insert(0, cfg.get("music_dir") or str(APP_DIR / "music"))
        self.sid.delete(0, "end")
        self.sid.insert(0, cfg.get("spotify_client_id", ""))
        self.ssec.delete(0, "end")
        self.ssec.insert(0, cfg.get("spotify_client_secret", ""))
        self.lfm.delete(0, "end")
        self.lfm.insert(0, cfg.get("lastfm_api_key", ""))
        codec, _, quality = settings.audio_preset(cfg).partition("_")
        self.fmt_var.set("MP3" if codec == "mp3" else "M4A")
        self.quality_var.set(quality)
        try:
            import yt_dlp
            ydl = yt_dlp.version.__version__
        except Exception:
            ydl = "не найден"
        ff = "найден" if shutil.which("ffmpeg") else "НЕ найден (нужен для загрузки и громкости)"
        self.info.configure(text=f"Программа: {APP_DIR}\nffmpeg: {ff}\nyt-dlp: {ydl}")

    def _pick(self):
        start = self.dir_entry.get().strip() or str(APP_DIR / "music")
        path = filedialog.askdirectory(parent=self.app, title="Папка с музыкой",
                                       initialdir=start if Path(start).exists() else str(APP_DIR))
        if path:
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, path)

    def _open(self):
        folder = Path(self.dir_entry.get().strip() or APP_DIR / "music")
        folder.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(folder)   # noqa: S606 - открыть папку в проводнике
        else:
            subprocess.Popen(["xdg-open", str(folder)])

    def _save(self):
        fmt = "mp3" if self.fmt_var.get().upper() == "MP3" else "m4a"
        quality = self.quality_var.get().strip()
        if quality not in ("128", "192", "256"):
            quality = "128"
        self.app.cfg.update({
            "music_dir": self.dir_entry.get().strip(),
            "spotify_client_id": self.sid.get().strip(),
            "spotify_client_secret": self.ssec.get().strip(),
            "lastfm_api_key": self.lfm.get().strip(),
            "audio_preset": f"{fmt}_{quality}",
        })
        accent_changed = self.app.cfg.get("accent_color") != self.accent
        self.app.cfg["accent_color"] = self.accent
        settings.save(self.app.cfg)
        if accent_changed:
            self.app.apply_accent(self.accent)
            self.app.say("Настройки сохранены; цвет применён. Остальные параметры действуют со следующей задачи.")
        else:
            self.app.say("Настройки сохранены; новые параметры действуют со следующей задачи.")

    def _check_updates(self):
        if getattr(self, "_checking", False):
            return self.app.say("Проверка уже идёт")
        self._checking = True
        self.app.say("Проверяю обновления инструментов…")
        threading.Thread(target=self._check_updates_work, daemon=True).start()

    def _check_updates_work(self):
        """Сеть - в отдельном потоке; результат уходит в лог через очередь событий
        (TK-виджеты из чужого потока не трогаем)."""
        from core import updates
        try:
            report = updates.check_all()
        except Exception as ex:  # noqa: BLE001 - отчёт не должен ронять окно
            report = f"Проверка обновлений не удалась: {ex}\n"
        finally:
            self._checking = False
        self.app.runner.events.put(("log", "\n" + report))

    def _set_accent(self, color):
        if not T.valid(color):
            return
        self.accent = color.lower()
        name = next((n for n, c in T.PRESETS if c == self.accent), "свой")
        self.accent_label.configure(text=f"● {name} {self.accent}", text_color=self.accent)

    def _pick_accent(self):
        _rgb, color = colorchooser.askcolor(color=self.accent, parent=self.app, title="Цвет оформления")
        if color:
            self._set_accent(color)

    def _save_restart(self):
        if self.app._job_running:
            return self.app.say("Дождитесь окончания задачи, потом перезапустите")
        self._save()
        args = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, str(APP_DIR / "app.py")]
        subprocess.Popen(args, cwd=str(APP_DIR))
        self.app.destroy()


class IpodPage(Page):
    title = "Передача на iPod"
    hint = ("Автономная запись аудио и iTunesDB без iTunes; проверено для iPod nano 2G. Перед записью "
            "создаётся резервная копия базы. Закройте iTunes; после передачи безопасно извлеките устройство.")
    NO_DEVICE = "iPod не найден"

    def build(self):
        self.devices = {}
        self._selected_files = []
        self._selection_display = ""
        self.body.grid_rowconfigure(0, weight=1)
        box = ctk.CTkScrollableFrame(self.body, fg_color="transparent")
        box.grid(row=0, column=0, sticky="nsew")
        box.grid_columnconfigure(1, weight=1)
        self.info = ctk.CTkLabel(box, text="Поиск iPod…", anchor="w", justify="left")
        self.info.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 4))

        ctk.CTkLabel(box, text="Устройство", anchor="w").grid(row=1, column=0, sticky="w", padx=(0, 12))
        self.device_menu = ctk.CTkOptionMenu(box, values=[self.NO_DEVICE])
        self.device_menu.grid(row=1, column=1, sticky="ew")
        ctk.CTkButton(box, text="Обновить", width=120, command=self.refresh).grid(
            row=1, column=2, padx=(8, 0))

        ctk.CTkLabel(box, text="Файлы или папка", anchor="w").grid(
            row=2, column=0, sticky="w", padx=(0, 12), pady=(6, 0))
        self.source_entry = ctk.CTkEntry(box)
        self.source_entry.grid(row=2, column=1, sticky="ew", pady=(6, 0))
        ctk.CTkButton(box, text="Выбрать…", width=120, command=self._pick).grid(
            row=2, column=2, padx=(8, 0), pady=(6, 0))

        ctk.CTkLabel(box, text="Плейлист (необязательно)", anchor="w").grid(
            row=3, column=0, sticky="w", padx=(0, 12), pady=(6, 0))
        self.playlist_entry = ctk.CTkEntry(box, placeholder_text="пусто - только в общую медиатеку")
        self.playlist_entry.grid(row=3, column=1, sticky="ew", pady=(6, 0))
        run = ctk.CTkButton(box, text="Передать", width=120, command=self._run)
        run.grid(row=3, column=2, padx=(8, 0), pady=(6, 0))
        self.app.run_buttons.append(run)

        self.with_artwork = ctk.BooleanVar(value=True)
        self.eject_after = ctk.BooleanVar(value=False)
        self.nano2g_confirm = ctk.BooleanVar(value=False)
        self.allow_other = ctk.BooleanVar(value=False)
        flags = ctk.CTkFrame(box, fg_color="transparent")
        flags.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        flags.grid_columnconfigure((0, 1), weight=1)
        options = [
            (self.with_artwork, "Добавлять обложки из тегов"),
            (self.eject_after, "Извлечь iPod после передачи"),
            (self.nano2g_confirm, "Это точно nano 2G (если модель не определилась)"),
            (self.allow_other, "Разрешить другие модели (экспериментально)"),
        ]
        for i, (var, text) in enumerate(options):
            ctk.CTkCheckBox(flags, text=text, variable=var).grid(
                row=i // 2, column=i % 2, sticky="w", pady=(0, 6))
        eject = ctk.CTkButton(box, text="Извлечь iPod", width=120, command=self._eject)
        eject.grid(row=4, column=2, padx=(8, 0), pady=(8, 0), sticky="n")
        self.app.run_buttons.append(eject)

    def refresh(self):
        try:
            devices = engine.find_ipods()
        except Exception as exc:
            devices = []
            self.info.configure(text=f"Ошибка поиска: {exc}")
        self.devices = {f"{d['root']}  {d['model']}": d for d in devices}
        names = list(self.devices) or [self.NO_DEVICE]
        current = self.device_menu.get()
        self.device_menu.configure(values=names)
        self.device_menu.set(current if current in self.devices else names[0])
        if devices:
            lines = [f"{d['root']}  {d['model']}: {d['status']}, свободно {d['free'] // 2**20} МБ"
                     for d in devices]
            self.info.configure(text="\n".join(lines))
        elif not self.info.cget("text").startswith("Ошибка"):
            self.info.configure(text="iPod не найден. Подключите устройство и убедитесь, что оно смонтировано "
                                     "как диск (режим «Использовать как диск»).")

    def _device_root(self):
        device = self.devices.get(self.device_menu.get())
        return str(device["root"]) if device else None

    def _pick(self):
        paths = filedialog.askopenfilenames(
            parent=self.app,
            title="Выберите аудиофайлы (можно выделить несколько)",
            filetypes=[("Аудиофайлы",
                        "*.mp3 *.m4a *.m4b *.aac *.wav *.aiff *.aif *.flac *.opus *.ogg *.wma")],
        )
        if paths:
            self._selected_files = list(paths)
            self._selection_display = f"Выбрано файлов: {len(paths)}"
            self.source_entry.delete(0, "end")
            self.source_entry.insert(0, self._selection_display)
            return

        folder = filedialog.askdirectory(parent=self.app, title="Или выберите папку")
        if folder:
            self._selected_files = []
            self._selection_display = ""
            self.source_entry.delete(0, "end")
            self.source_entry.insert(0, folder)

    def _run(self):
        value = self.source_entry.get().strip()
        if self._selected_files and value == self._selection_display:
            files = [audio for path in self._selected_files for audio in engine.collect_audio(path)]
        else:
            self._selected_files = []
            self._selection_display = ""
            if not value:
                return self.app.say("Выберите файлы или папку")
            if not Path(value).exists():
                return self.app.say("Путь не существует")
            files = engine.collect_audio(value)
        if not files:
            return self.app.say("Аудиофайлы не найдены")
        root = self._device_root()
        if not root:
            self.refresh()
            root = self._device_root()
            if not root:
                return self.app.say("iPod не найден")
        kwargs = dict(device_root=root, assume_nano2g=self.nano2g_confirm.get(),
                      allow_other_models=self.allow_other.get(), with_artwork=self.with_artwork.get(),
                      playlist_name=self.playlist_entry.get().strip(), eject_after=self.eject_after.get())
        self.app.start_job("Передача на iPod", lambda: engine.run_ipod(files, **kwargs))

    def _eject(self):
        root = self._device_root()
        if not root:
            return self.app.say("iPod не найден")
        self.app.start_job("Извлечение iPod", lambda: engine.eject_ipod(root))


class LibraryPage(Page):
    title = "Медиатека iPod"
    hint = ("Список треков на iPod: правка тегов в базе iPod и удаление треков вместе с файлами. "
            "Перед каждой записью создаётся резервная копия базы; iTunes должен быть закрыт.")
    host_height = 560
    NO_DEVICE = "iPod не найден"
    COLUMNS = (("title", "Название", 220), ("artist", "Исполнитель", 160), ("album", "Альбом", 160),
               ("genre", "Жанр", 90), ("year", "Год", 50), ("track_number", "№", 40),
               ("duration", "Длит.", 60))
    FIELDS = (("title", "Название"), ("artist", "Исполнитель"), ("album", "Альбом"),
              ("albumartist", "Исп. альбома"), ("genre", "Жанр"), ("year", "Год"),
              ("track_number", "№ трека"))

    def build(self):
        self.devices, self.rows, self.shown = {}, [], []
        self._result, self._sort = None, ("artist", False)
        self.body.grid_rowconfigure(1, weight=1)
        top = ctk.CTkFrame(self.body, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(4, weight=1)
        self.device_menu = ctk.CTkOptionMenu(top, values=[self.NO_DEVICE], width=260)
        self.device_menu.grid(row=0, column=0)
        ctk.CTkButton(top, text="Найти iPod", width=110, command=self._find).grid(row=0, column=1, padx=(8, 0))
        load = ctk.CTkButton(top, text="Загрузить треки", width=140, command=self._load)
        load.grid(row=0, column=2, padx=(8, 0))
        self.app.run_buttons.append(load)
        eject = ctk.CTkButton(top, text="Безопасно извлечь", width=145, command=self._eject)
        eject.grid(row=0, column=3, padx=(8, 0))
        self.app.run_buttons.append(eject)
        self.search = ctk.CTkEntry(top, placeholder_text="поиск: название, исполнитель, альбом")
        self.search.grid(row=0, column=4, sticky="ew", padx=(8, 0))
        self.search.bind("<KeyRelease>", lambda e: self._fill())

        style = ttk.Style(self)  # тему ttk не переключаем: theme_use() ломает обработку событий CustomTkinter
        style.configure("Lib.Treeview", background=T.BG, fieldbackground=T.BG,
                        foreground=T.TEXT, rowheight=22, borderwidth=0)
        try:  # заголовки системной темы Windows не красятся - берём элементы темы default
            for part in ("cell", "border", "padding", "image", "text"):
                if f"Lib.Treeheading.{part}" not in style.element_names():
                    style.element_create(f"Lib.Treeheading.{part}", "from", "default")
            style.layout("Lib.Treeview.Heading", [
                ("Lib.Treeheading.cell", {"sticky": "nswe"}),
                ("Lib.Treeheading.border", {"sticky": "nswe", "children": [
                    ("Lib.Treeheading.padding", {"sticky": "nswe", "children": [
                        ("Lib.Treeheading.image", {"side": "right", "sticky": ""}),
                        ("Lib.Treeheading.text", {"sticky": "we"})]})]})])
            style.configure("Lib.Treeview.Heading", background=T.CARD_BORDER, foreground=T.TEXT,
                            relief="flat", borderwidth=0, padding=(6, 4))
            style.map("Lib.Treeview.Heading", background=[("active", T.NAV_HOVER)])
        except Exception:  # noqa: BLE001
            style.configure("Lib.Treeview.Heading", foreground="#1d2027")
        style.map("Lib.Treeview", background=[("selected", T.NAV_ACTIVE)])
        table = ctk.CTkFrame(self.body, fg_color="transparent")
        table.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        table.grid_columnconfigure(0, weight=1)
        table.grid_rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(table, columns=[c for c, _t, _w in self.COLUMNS], show="headings",
                                 selectmode="extended", style="Lib.Treeview")
        for col, text, width in self.COLUMNS:
            self.tree.heading(col, text=text, command=lambda c=col: self._sort_by(c))
            self.tree.column(col, width=width, stretch=col in ("title", "artist", "album"))
        self.tree.grid(row=0, column=0, sticky="nsew")
        bar = ctk.CTkScrollbar(table, command=self.tree.yview)
        bar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=bar.set)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._on_select())
        self.tree.bind("<Control-a>", lambda e: self._select_all() or "break")
        self.tree.bind("<Control-A>", lambda e: self._select_all() or "break")

        form = ctk.CTkFrame(self.body, fg_color="transparent")
        form.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.entries, self._initial = {}, {}
        for i, (key, text) in enumerate(self.FIELDS):
            r, c = divmod(i, 4)
            ctk.CTkLabel(form, text=text, anchor="w").grid(row=r, column=c * 2, sticky="w", padx=(0, 6), pady=2)
            entry = ctk.CTkEntry(form, width=60 if key in ("year", "track_number") else 150)
            entry.grid(row=r, column=c * 2 + 1, sticky="ew", padx=(0, 12), pady=2)
            self.entries[key] = entry
        for c in (1, 3, 5):
            form.grid_columnconfigure(c, weight=1)

        bottom = ctk.CTkFrame(self.body, fg_color="transparent")
        bottom.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        save = ctk.CTkButton(bottom, text="Сохранить изменения", width=180, command=self._save)
        save.pack(side="left")
        delete = ctk.CTkButton(bottom, text="Удалить выбранные", width=160, fg_color=T.DANGER,
                               hover_color=T.DANGER_HOVER, command=self._delete)
        delete.pack(side="left", padx=(8, 0))
        ctk.CTkButton(bottom, text="Выбрать все", width=120, command=self._select_all).pack(
            side="left", padx=(8, 0))
        self.app.run_buttons += [save, delete]
        self.count = ctk.CTkLabel(bottom, text="", anchor="e")
        self.count.pack(side="right")

    # --- устройство и загрузка ---

    def refresh(self):
        if not self.devices:
            self._find()

    def _find(self):
        try:
            devices = engine.find_ipods()
        except Exception as exc:
            devices = []
            self.app.say(f"Ошибка поиска: {exc}")
        self.devices = {f"{d['root']}  {d['model']}": d for d in devices}
        names = list(self.devices) or [self.NO_DEVICE]
        self.device_menu.configure(values=names)
        self.device_menu.set(self.device_menu.get() if self.device_menu.get() in self.devices else names[0])

    def _device_root(self):
        device = self.devices.get(self.device_menu.get())
        if not device:
            self.app.say("iPod не найден - подключите его и нажмите «Найти iPod»")
        return str(device["root"]) if device else None

    def _flags(self):
        ipod = self.app.pages.get("ipod")
        if not ipod:
            return {}
        return dict(assume_nano2g=ipod.nano2g_confirm.get(), allow_other_models=ipod.allow_other.get())

    def _job(self, title, action, root):
        def work():
            if action:
                action()
            self._result = engine.ipod_tracks(root)
        self._result = None
        self.app.start_job(title, work)
        self.after(300, self._wait)

    def _wait(self):
        if self.app._job_running:
            return self.after(300, self._wait)
        if self._result is not None:
            self.rows, self._result = self._result, None
            self._fill()

    def _load(self):
        root = self._device_root()
        if root:
            self._job("Чтение медиатеки iPod", None, root)

    def _eject(self):
        if self.app._job_running:
            return self.app.say("Дождитесь окончания текущей задачи перед извлечением")
        root = self._device_root()
        if not root:
            return
        if not messagebox.askyesno(
                "Безопасное извлечение",
                f"Безопасно извлечь iPod ({root})?\n\nУбедитесь, что передача и редактирование завершены.",
                parent=self.app):
            return
        self.app.start_job("Безопасное извлечение iPod", lambda: engine.eject_ipod(root))
        self.after(300, self._refresh_after_eject)

    def _refresh_after_eject(self):
        if self.app._job_running:
            return self.after(300, self._refresh_after_eject)
        self._find()

    # --- таблица ---

    def _sort_by(self, col):
        key, rev = self._sort
        self._sort = (col, not rev if key == col else False)
        self._fill()

    def _fill(self):
        query = self.search.get().strip().lower()
        key, rev = self._sort
        rows = [r for r in self.rows if not query or query in
                f"{r['title']} {r['artist']} {r['album']} {r['albumartist']}".lower()]
        numeric = key in ("year", "track_number", "duration")
        rows.sort(key=lambda r: (r[key] if numeric else str(r[key]).lower(),
                                 str(r["album"]).lower(), r["track_number"]), reverse=rev)
        self.shown = rows
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(rows):
            values = [r[c] or "" for c, _t, _w in self.COLUMNS]
            values[-1] = f"{r['duration'] // 60}:{r['duration'] % 60:02d}"
            self.tree.insert("", "end", iid=str(i), values=values)
        self.count.configure(text=f"Показано {len(rows)} из {len(self.rows)}")
        self._on_select()

    def _select_all(self):
        items = self.tree.get_children()
        if self.tree.selection() == items:
            self.tree.selection_remove(*items)
        else:
            self.tree.selection_set(items)

    def _selected(self):
        return [self.shown[int(i)] for i in self.tree.selection()]

    def _on_select(self):
        rows = self._selected()
        self._initial = {}
        for key, entry in self.entries.items():
            values = {str(r[key] or "") for r in rows}
            value = values.pop() if len(values) == 1 else ""
            entry.delete(0, "end")
            entry.insert(0, value)
            self._initial[key] = value
        if rows:
            self.count.configure(text=f"Выбрано {len(rows)} из {len(self.rows)}")

    # --- изменения ---

    def _save(self):
        rows, root = self._selected(), self._device_root()
        if not rows or not root:
            return self.app.say("Выберите треки в списке")
        fields = {k: e.get() for k, e in self.entries.items() if e.get() != self._initial.get(k, "")}
        if not fields:
            return self.app.say("Поля не изменены")
        dbids, flags = [r["dbid"] for r in rows], self._flags()
        self._job("Изменение тегов на iPod", lambda: engine.ipod_edit(root, dbids, fields, **flags), root)

    def _delete(self):
        rows, root = self._selected(), self._device_root()
        if not rows or not root:
            return self.app.say("Выберите треки в списке")
        names = "\n".join(f"{r['artist']} - {r['title']}" for r in rows[:10])
        more = f"\n…и ещё {len(rows) - 10}" if len(rows) > 10 else ""
        if not messagebox.askyesno("Удаление с iPod", f"Удалить с iPod треков: {len(rows)}?\n\n{names}{more}\n\n"
                                   "Аудиофайлы будут удалены с устройства.", parent=self.app):
            return
        dbids, flags = [r["dbid"] for r in rows], self._flags()
        self._job("Удаление треков с iPod", lambda: engine.ipod_delete(root, dbids, **flags), root)


PAGES = [
    ("download", "Загрузка списка", DownloadPage),
    ("link", "По ссылке", LinkPage),
    ("manual", "Ручной разбор", ManualPage),
    ("retag", "Теги", RetagPage),
    ("covers", "Обложки", CoversPage),
    ("gain", "Громкость", GainPage),
    ("ipod", "Передача на iPod", IpodPage),
    ("library", "Медиатека iPod", LibraryPage),
    ("settings", "Настройки", SettingsPage),
]
