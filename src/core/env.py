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
    # ffmpeg/ffprobe ищутся через PATH - так их видят и subprocess-вызовы движка, и yt-dlp.
    # tools/bin и bin рядом с программой идут раньше встроенных в exe: их можно
    # обновить из самой программы, не пересобирая exe (core/tool_updates.py).
    paths = [APP_DIR / "tools" / "bin"]
    if FROZEN:
        paths.append(APP_DIR / "bin")
    paths.append(BUNDLE_DIR / "bin")
    dirs = [str(p) for p in paths if p.is_dir()]
    if dirs:
        os.environ["PATH"] = os.pathsep.join(dirs) + os.pathsep + os.environ.get("PATH", "")
    prefer_external_packages(APP_DIR / "tools" / "lib")
    _hide_console_windows()
    # все относительные файлы движка (report.csv, meta_cache.json, логи, music) - рядом с приложением
    os.chdir(APP_DIR)


def prefer_external_packages(directory):
    """Пакеты из внешней папки важнее встроенных в exe.

    PyInstaller ищет модули в своём архиве раньше, чем на диске, поэтому одним
    sys.path не обойтись: свой finder встаёт в начало sys.meta_path и берёт
    пакеты из directory (например, свежий yt-dlp из tools/lib).
    """
    directory = Path(directory)
    if not directory.is_dir():
        return
    names = set()
    for item in directory.iterdir():
        if item.is_dir():
            names.add(item.name)
        elif item.suffix.lower() in (".py", ".pyd", ".so"):
            names.add(item.stem)
    if not names:
        return

    import importlib.abc
    import importlib.machinery

    class _ExternalFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.partition(".")[0] not in names:
                return None
            return importlib.machinery.PathFinder.find_spec(fullname, path, target)

    sys.path.insert(0, str(directory))
    sys.meta_path.insert(0, _ExternalFinder())


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
