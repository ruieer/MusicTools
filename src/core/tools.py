"""Проверка наличия и версий всех инструментов перед запуском.

Внешние бинарники (ffmpeg/ffprobe) и Python-пакеты. Отчёт - для лога окна.
Сети не касается: только локальная проверка (shutil.which, импорт, метаданные).
"""
import re
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version as pkg_version

_BIN_TIMEOUT = 12

# (метка, импорт-имя, имя дистрибутива, зачем нужно)
PACKAGES = [
    ("customtkinter", "customtkinter", "customtkinter", "интерфейс"),
    ("yt-dlp", "yt_dlp", "yt-dlp", "скачивание с YouTube/SoundCloud"),
    ("mutagen", "mutagen", "mutagen", "теги и обложки"),
    ("rapidfuzz", "rapidfuzz", "rapidfuzz", "сопоставление треков"),
    ("requests", "requests", "requests", "метаданные из сети"),
    ("Pillow", "PIL", "Pillow", "обработка обложек"),
    ("pygpod", "pygpod", "pygpod", "передача на iPod"),
]


def _bin_version(name):
    """(найден_и_работает, строка_версии) для ffmpeg/ffprobe."""
    exe = shutil.which(name)
    if not exe:
        return False, "НЕ найден - положите в bin\\ или в PATH"
    try:
        r = subprocess.run([exe, "-version"], capture_output=True, timeout=_BIN_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as ex:
        return False, f"найден, но не запускается ({ex})"
    if r.returncode != 0:
        return False, "найден, но не запускается"
    out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
    m = re.search(r"version\s+(\S+)", out)
    return True, (m.group(1) if m else "ok")


def _pkg_version(import_name, dist_name):
    """(загружается, строка_версии) для Python-пакета."""
    try:
        __import__(import_name)
    except Exception as ex:  # noqa: BLE001 - любой сбой импорта = не установлен
        return False, f"НЕ установлен ({type(ex).__name__})"
    try:
        return True, pkg_version(dist_name)
    except PackageNotFoundError:
        mod = sys.modules.get(import_name)
        return True, str(getattr(mod, "__version__", "версия неизвестна"))


def report() -> str:
    """Готовый отчёт для лога: версии всех инструментов и итог по отсутствующим."""
    lines = ["Проверка инструментов перед запуском:\n"]
    missing = []

    def add(ok, label, ver, why):
        status = "есть" if ok else "нет "
        lines.append(f"  [{status}] {label:<13} {ver}  -  {why}")
        if not ok:
            missing.append(label)

    ok, ver = _bin_version("ffmpeg")
    add(ok, "ffmpeg", ver, "загрузка, перекодировка, громкость, теги")
    ok, ver = _bin_version("ffprobe")
    add(ok, "ffprobe", ver, "проверка длительности трека")
    lines.append(f"  [ -- ] {'Python':<13} {sys.version.split()[0]}  -  среда выполнения")

    for label, imp, dist, why in PACKAGES:
        ok, ver = _pkg_version(imp, dist)
        add(ok, label, ver, why)

    lines.append("")
    if missing:
        lines.append(f"Внимание: недоступно - {', '.join(missing)}. Часть функций работать не будет.")
    else:
        lines.append("Все инструменты найдены - можно работать.")
    return "\n".join(lines) + "\n"
