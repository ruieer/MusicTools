"""Проверка обновлений внешних инструментов: yt-dlp, ffmpeg, Python-пакеты.

Сеть используется только по явному запросу (кнопка «Проверить обновления»
в Настройках), автоматических запросов при старте нет.
- Python-пакеты сравниваются с последними версиями на PyPI;
- ffmpeg - с release-version сборки essentials с gyan.dev.

В собранном exe обновить пакеты через pip нельзя: отчёт подсказывает, что нужна
новая сборка. В исходниках печатается готовая команда pip.
"""
import json
import re
import sys
import urllib.request
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version

from core import tools
from core.i18n import tr

TIMEOUT = 8
UA = {"User-Agent": "MusicTools update check (personal music tool)"}
FFMPEG_VERSION_URL = "https://www.gyan.dev/ffmpeg/builds/release-version"
FFMPEG_DOWNLOAD = "https://www.gyan.dev/ffmpeg/builds/ (сборка essentials)"
PYPI_URL = "https://pypi.org/pypi/{}/json"


def _open(url):
    request = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(request, timeout=TIMEOUT)


def _pypi_latest(dist: str) -> str:
    """Последняя версия дистрибутива на PyPI или '' при ошибке."""
    try:
        with _open(PYPI_URL.format(dist)) as response:
            return str(json.loads(response.read().decode("utf-8"))["info"]["version"])
    except Exception:  # noqa: BLE001 - любая сетевая/JSON-ошибка = "не проверить"
        return ""


def _ffmpeg_latest() -> str:
    try:
        with _open(FFMPEG_VERSION_URL) as response:
            return response.read().decode("utf-8", "replace").strip().splitlines()[0].strip()
    except Exception:  # noqa: BLE001
        return ""


def _version_tuple(text) -> tuple:
    numbers = re.findall(r"\d+", str(text or ""))
    return tuple(int(n) for n in numbers[:4])


def is_newer(latest, installed) -> bool:
    """True, если latest новее installed. Нечисловые версии считаем равными."""
    new, old = _version_tuple(latest), _version_tuple(installed)
    if not new or not old:
        return False
    return new > old


def _installed_package(import_name: str, dist_name: str):
    """(версия или '', работает ли пакет)."""
    try:
        __import__(import_name)
    except Exception:  # noqa: BLE001 - сбой импорта = не установлен
        return "", False
    try:
        return pkg_version(dist_name), True
    except PackageNotFoundError:
        module = sys.modules.get(import_name)
        return str(getattr(module, "__version__", "")), True


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def check_all() -> str:
    """Отчёт для лога: что устарело и как обновить."""
    lines = [tr("Проверка обновлений инструментов:") + "\n"]
    updates = []
    failed = []
    stale = tr("не удалось узнать последнюю версию")
    current = tr("актуальная версия")

    ok, ffmpeg_version = tools._bin_version("ffmpeg")
    if ok:
        latest = _ffmpeg_latest()
        if not latest:
            failed.append("ffmpeg")
            lines.append(tr("  [ ? ] {label}  {ver}  -  {why}",
                            label=f"{'ffmpeg':<13}", ver=ffmpeg_version, why=stale))
        elif is_newer(latest, ffmpeg_version):
            updates.append(f"ffmpeg {ffmpeg_version} → {latest}")
            lines.append(tr("  [ ! ] {label}  {old} → {new}  -  скачайте из {where}",
                            label=f"{'ffmpeg':<13}", old=ffmpeg_version, new=latest,
                            where=FFMPEG_DOWNLOAD))
        else:
            lines.append(tr("  [ ok] {label}  {ver}  -  {why}",
                            label=f"{'ffmpeg':<13}", ver=ffmpeg_version, why=current))
    else:
        lines.append(tr("  [ -- ] {label}  {ver}  -  обновлять нечего",
                        label=f"{'ffmpeg':<13}", ver=ffmpeg_version))

    for label, import_name, dist_name, _why in tools.PACKAGES:
        installed, available = _installed_package(import_name, dist_name)
        if not available:
            lines.append(tr("  [ -- ] {label}  НЕ установлен  -  pip install {dist}",
                            label=f"{label:<13}", dist=dist_name))
            continue
        latest = _pypi_latest(dist_name)
        if not latest:
            failed.append(label)
            lines.append(tr("  [ ? ] {label}  {ver}  -  {why}",
                            label=f"{label:<13}", ver=installed, why=stale))
            continue
        if is_newer(latest, installed):
            updates.append(f"{label} {installed} → {latest}")
            lines.append(tr("  [ ! ] {label}  {old} → {new}  -  есть новая версия",
                            label=f"{label:<13}", old=installed, new=latest))
        else:
            lines.append(tr("  [ ok] {label}  {ver}  -  {why}",
                            label=f"{label:<13}", ver=installed, why=current))

    lines.append("")
    if failed:
        lines.append(tr("Не удалось проверить (нет сети или сервис недоступен): {names}.",
                        names=", ".join(failed)))
    if updates:
        lines.append(tr("Доступны обновления: {n}.", n=len(updates)))
        if any(item.startswith("ffmpeg ") for item in updates):
            lines.append(tr("ffmpeg обновляется заменой bin/ffmpeg.exe и bin/ffprobe.exe."))
        packages = [dist for label, _imp, dist, _w in tools.PACKAGES
                    if any(item.startswith(label + " ") for item in updates)]
        if packages:
            if _frozen():
                lines.append(tr("Программа собрана в exe - встроенные пакеты обновляются только новой сборкой:"))
                lines.append(tr("  пересоберите MusicTools (pyinstaller MusicTools.spec) и замените exe."))
                if any(item.startswith("yt-dlp ") for item in updates):
                    lines.append(tr("  Если сломалось скачивание с YouTube, новая сборка со свежим "
                                    "yt-dlp обычно решает проблему."))
            else:
                lines.append(tr("Обновить: pip install -U {names}", names=" ".join(packages)))
    else:
        lines.append(tr("Все проверенные инструменты актуальны."))
    return "\n".join(lines) + "\n"
