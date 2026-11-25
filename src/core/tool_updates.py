"""Обновление инструментов без пересборки exe: yt-dlp и ffmpeg/ffprobe.

Скачанное кладётся рядом с программой и перекрывает то, что вшито в exe:
- tools/lib/<пакет>  - папка ставится в начало sys.path (env.prefer_external_packages);
- tools/bin/ffmpeg.exe, ffprobe.exe - папка ставится в начало PATH (env.setup).

Источники: PyPI (yt-dlp, чистый Python) и gyan.dev (сборка essentials ffmpeg).
"""
import json
import os
import re
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from core import env, updates
from core.i18n import tr

TIMEOUT = 30
CHUNK = 262144
UA = {"User-Agent": "MusicTools tool updater"}
PYPI_YTDLP = "https://pypi.org/pypi/yt-dlp/json"
FFMPEG_VERSION_URL = "https://www.gyan.dev/ffmpeg/builds/release-version"
FFMPEG_ZIP = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
YTDLP_PACKAGE = "yt_dlp"
FFMPEG_BINARIES = ("ffmpeg.exe", "ffprobe.exe")


# --- пути -------------------------------------------------------------------

def tools_dir(root=None) -> Path:
    return (Path(root) if root else env.APP_DIR) / "tools"


def lib_dir(root=None) -> Path:
    return tools_dir(root) / "lib"


def bin_dir(root=None) -> Path:
    return tools_dir(root) / "bin"


# --- сеть -------------------------------------------------------------------

def _open(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=TIMEOUT)


def _download(url, dest: Path, progress=None) -> Path:
    """Скачать файл в dest, сообщая progress(скачано, всего)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with _open(url) as response, open(dest, "wb") as file:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = response.read(CHUNK)
            if not chunk:
                break
            file.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    if done < 4096:
        raise RuntimeError(tr("скачался пустой файл"))
    return dest


def _percent_log(say, name):
    """Печатать прогресс примерно каждые 10%."""
    last = [-10]

    def progress(done, total):
        if not total:
            return
        pct = min(int(done * 100 / total), 100)
        if pct >= last[0] + 10 or pct == 100:
            last[0] = pct
            say(tr("{name}: скачано {pct}%", name=name, pct=pct))

    return progress


# --- yt-dlp -----------------------------------------------------------------

def external_ytdlp(root=None) -> str:
    """Версия yt-dlp из tools/lib или '' - читаем файл, не импортируя пакет."""
    path = lib_dir(root) / YTDLP_PACKAGE / "version.py"
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"""__version__\s*=\s*['"]?([0-9][^'"\s]*)""", text)
    return match.group(1) if match else ""


def installed_ytdlp() -> str:
    """Версия загруженного в текущий процесс yt-dlp (в exe - встроенного)."""
    try:
        import yt_dlp
        return str(getattr(yt_dlp.version, "__version__", "") or "")
    except Exception:  # noqa: BLE001 - нет пакета или сломан импорт
        return ""


def latest_ytdlp() -> dict:
    """{version, url, size} последнего релиза yt-dlp на PyPI."""
    with _open(PYPI_YTDLP) as response:
        data = json.loads(response.read().decode("utf-8"))
    version = str(data["info"]["version"])
    wheel = next((item for item in data.get("urls") or []
                  if item.get("packagetype") == "bdist_wheel"
                  and str(item.get("filename", "")).endswith("-py3-none-any.whl")), None)
    if not wheel:
        raise RuntimeError(tr("на PyPI нет подходящего файла yt-dlp"))
    return {"version": version, "url": wheel["url"], "size": int(wheel.get("size") or 0)}


def install_ytdlp(wheel_url, root=None, progress=None) -> str:
    """Распаковать wheel в tools/lib и вернуть установленную версию."""
    target = lib_dir(root)
    target.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="musictools_ytdlp_"))
    try:
        wheel = _download(wheel_url, tmp / "yt-dlp.whl", progress)
        unpack = tmp / "unpacked"
        with zipfile.ZipFile(wheel) as archive:
            members = [name for name in archive.namelist()
                       if name.startswith(YTDLP_PACKAGE + "/") and not name.endswith("/")]
            if not members:
                raise RuntimeError(tr("в скачанном файле нет пакета {name}", name=YTDLP_PACKAGE))
            archive.extractall(unpack, members=members)
        final = target / YTDLP_PACKAGE
        old = target / (YTDLP_PACKAGE + ".old")
        shutil.rmtree(old, ignore_errors=True)
        if final.is_dir():
            final.rename(old)
        shutil.move(str(unpack / YTDLP_PACKAGE), str(final))
        shutil.rmtree(old, ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return external_ytdlp(root)


# --- ffmpeg -----------------------------------------------------------------

def current_ffmpeg() -> str:
    from core import tools
    ok, version = tools._bin_version("ffmpeg")
    return version if ok else ""


def latest_ffmpeg() -> str:
    with _open(FFMPEG_VERSION_URL) as response:
        text = response.read().decode("utf-8", "replace").strip()
    return text.splitlines()[0].strip() if text else ""


def install_ffmpeg(zip_url=None, root=None, progress=None) -> dict:
    """Скачать сборку essentials и положить ffmpeg.exe/ffprobe.exe в tools/bin."""
    target = bin_dir(root)
    target.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="musictools_ffmpeg_"))
    try:
        archive = _download(zip_url or FFMPEG_ZIP, tmp / "ffmpeg.zip", progress)
        written = {}
        with zipfile.ZipFile(archive) as zf:
            for name in zf.namelist():
                normal = name.replace("\\", "/")
                base = normal.rsplit("/", 1)[-1].lower()
                if base not in FFMPEG_BINARIES or "/bin/" not in normal:
                    continue
                dest = target / base
                with zf.open(name) as src, open(dest, "wb") as out:
                    shutil.copyfileobj(src, out, CHUNK)
                written[base] = dest.stat().st_size
        missing = [name for name in FFMPEG_BINARIES if name not in written]
        if missing:
            raise RuntimeError(tr("в архиве нет файлов: {names}", names=", ".join(missing)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # новые бинарники должны подхватиться сразу, без перезапуска
    parts = os.environ.get("PATH", "").split(os.pathsep)
    if str(target) not in parts:
        os.environ["PATH"] = str(target) + os.pathsep + os.environ.get("PATH", "")
    return written


# --- общий отчёт ------------------------------------------------------------

def update_all(root=None, log=None) -> str:
    """Обновить yt-dlp и ffmpeg, если вышли новее. Возвращает отчёт для лога."""
    say = log or (lambda _text: None)
    lines = []
    restart = False

    try:
        latest = latest_ytdlp()
        have = external_ytdlp(root) or installed_ytdlp()
        if updates.is_newer(latest["version"], have):
            say(tr("Скачиваю yt-dlp {old} → {new}…", old=have or "-", new=latest["version"]))
            version = install_ytdlp(latest["url"], root, _percent_log(say, "yt-dlp"))
            lines.append(tr("yt-dlp обновлён до {v} (лежит в tools/lib)", v=version))
            restart = True
        else:
            lines.append(tr("yt-dlp {v} - уже последний", v=have or "-"))
    except Exception as ex:  # noqa: BLE001 - отчёт не должен ронять окно
        lines.append(tr("yt-dlp обновить не удалось: {ex}", ex=ex))

    try:
        latest = latest_ffmpeg()
        have = current_ffmpeg()
        if not latest:
            lines.append(tr("ffmpeg: не удалось узнать последнюю версию"))
        elif updates.is_newer(latest, have):
            say(tr("Скачиваю ffmpeg {old} → {new} (около 110 МБ)…", old=have or "-", new=latest))
            install_ffmpeg(FFMPEG_ZIP, root, _percent_log(say, "ffmpeg"))
            lines.append(tr("ffmpeg обновлён до {v} (лежит в tools/bin)", v=latest))
        else:
            lines.append(tr("ffmpeg {v} - уже последний", v=have or "-"))
    except Exception as ex:  # noqa: BLE001
        lines.append(tr("ffmpeg обновить не удалось: {ex}", ex=ex))

    if restart:
        lines.append(tr("Перезапустите программу, чтобы новый yt-dlp заработал."))
    return "\n".join(lines) + "\n"
