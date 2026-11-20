"""Пути приложения и окружение.

Работает и из исходников (python app.py), и из собранного PyInstaller-exe.
- APP_DIR: папка, где лежит exe (или проект). Там живут config.json, report.csv,
  meta_cache.json, логи и папка music по умолчанию - как и раньше, рядом со скриптами.
- BUNDLE_DIR: место, где PyInstaller распаковал встроенные файлы (ffmpeg).
"""
import os
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))

if FROZEN:
    APP_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
else:
    APP_DIR = Path(__file__).resolve().parents[2]   # корень проекта: src/core/env.py -> корень
    BUNDLE_DIR = APP_DIR
    # в исходниках движок лежит отдельной папкой и импортируется как обычные модули
    sys.path.insert(0, str(APP_DIR / "src" / "engine"))


def setup():
    """Вызвать один раз при старте, до импорта движка."""
    # ffmpeg/ffprobe, встроенные в exe, должны находиться через PATH:
    # так их видят и subprocess-вызовы движка, и yt-dlp.
    bundled = BUNDLE_DIR / "bin"
    if bundled.is_dir():
        os.environ["PATH"] = str(bundled) + os.pathsep + os.environ.get("PATH", "")
    _hide_console_windows()
    # все относительные файлы движка (report.csv, meta_cache.json, логи, music) - рядом с приложением
    os.chdir(APP_DIR)


def _hide_console_windows():
    """В оконном exe каждый дочерний процесс (ffmpeg, powershell из pygpod и т.п.)
    открывал бы чёрное окно консоли - по умолчанию запускаем их без окна."""
    if sys.platform != "win32":
        return
    import subprocess
    if getattr(subprocess.Popen, "_musictools_no_window", False):
        return
    no_window = subprocess.CREATE_NO_WINDOW
    console_flags = subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS | no_window
    original = subprocess.Popen.__init__

    def __init__(self, *args, **kwargs):
        flags = kwargs.get("creationflags", 0) or 0
        if not flags & console_flags:
            kwargs["creationflags"] = flags | no_window
        original(self, *args, **kwargs)

    subprocess.Popen.__init__ = __init__
    subprocess.Popen._musictools_no_window = True
