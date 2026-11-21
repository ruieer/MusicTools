"""Проверка наличия и версий всех инструментов перед запуском.

Внешние бинарники (ffmpeg/ffprobe) и Python-пакеты. Отчёт - для лога окна.
Сети не касается: только локальная проверка (shutil.which, импорт, метаданные).
"""
import re
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version as pkg_version

from core.i18n import tr

_BIN_TIMEOUT = 12

# (метка, импорт-имя, имя дистрибутива, зачем нужно)
PACKAGES = [
    ("customtkinter", "customtkinter", "customtkinter", tr("интерфейс")),
    ("yt-dlp", "yt_dlp", "yt-dlp", tr("скачивание с YouTube/SoundCloud")),
    ("mutagen", "mutagen", "mutagen", tr("теги и обложки")),
    ("rapidfuzz", "rapidfuzz", "rapidfuzz", tr("сопоставление треков")),
    ("requests", "requests", "requests", tr("метаданные из сети")),
    ("Pillow", "PIL", "Pillow", tr("обработка обложек")),
    ("pygpod", "pygpod", "pygpod", tr("передача на iPod")),
]


def _bin_version(name):
    """(найден_и_работает, строка_версии) для ffmpeg/ffprobe."""
    exe = shutil.which(name)
    if not exe:
        return False, tr("НЕ найден - положите в bin или в PATH")
    try:
        r = subprocess.run([exe, "-version"], capture_output=True, timeout=_BIN_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as ex:
        return False, tr("найден, но не запускается ({ex})", ex=ex)
    if r.returncode != 0:
        return False, tr("найден, но не запускается")
    out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
    m = re.search(r"version\s+(\S+)", out)
    return True, (m.group(1) if m else "ok")


def _pkg_version(import_name, dist_name):
    """(загружается, строка_версии) для Python-пакета."""
    try:
        __import__(import_name)
    except Exception as ex:  # noqa: BLE001 - любой сбой импорта = не установлен
        return False, tr("НЕ установлен ({kind})", kind=type(ex).__name__)
    try:
        return True, pkg_version(dist_name)
    except PackageNotFoundError:
        mod = sys.modules.get(import_name)
        return True, str(getattr(mod, "__version__", tr("версия неизвестна")))


def report() -> str:
    """Готовый отчёт для лога: версии всех инструментов и итог по отсутствующим."""
    lines = [tr("Проверка инструментов перед запуском:") + "\n"]
    missing = []

    def add(ok, label, ver, why):
        status = tr("есть") if ok else tr("нет")
        lines.append(tr("  [{status}] {label}  {ver}  -  {why}",
                        status=status, label=f"{label:<13}", ver=ver, why=why))
        if not ok:
            missing.append(label)

    ok, ver = _bin_version("ffmpeg")
    add(ok, "ffmpeg", ver, tr("загрузка, перекодировка, громкость, теги"))
    ok, ver = _bin_version("ffprobe")
    add(ok, "ffprobe", ver, tr("проверка длительности трека"))
    lines.append(tr("  [ -- ] {label}  {ver}  -  {why}",
                    label=f"{'Python':<13}", ver=sys.version.split()[0],
                    why=tr("среда выполнения")))

    for label, imp, dist, why in PACKAGES:
        ok, ver = _pkg_version(imp, dist)
        add(ok, label, ver, why)

    lines.append("")
    if missing:
        lines.append(tr("Внимание: недоступно - {names}. Часть функций работать не будет.",
                        names=", ".join(missing)))
    else:
        lines.append(tr("Все инструменты найдены - можно работать."))
    return "\n".join(lines) + "\n"
