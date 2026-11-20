"""Автономная передача музыки на iPod (без iTunes) для томов, смонтированных в Windows.

Основная цель - iPod nano 2G. Другие модели, которые pygpod умеет записывать
(классические iPod, mini, nano 1G/3G/4G, video, classic), разрешены только
по явному подтверждению пользователя. Shuffle и nano 5G+ (SQLite-база) не поддерживаются.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import warnings
from datetime import datetime
from pathlib import Path

import windows_eject
from core.env import APP_DIR

COMPATIBLE = {".mp3", ".m4a", ".m4b", ".aac", ".wav", ".aiff", ".aif"}
AUDIO_EXTS = COMPATIBLE | {".flac", ".opus", ".ogg", ".wma"}
DEVICE_DATABASES = (
    ("iPod_Control/iTunes/iTunesDB", "iTunesDB"),
    ("iPod_Control/iTunes/iTunesCDB", "iTunesCDB"),
    ("iPod_Control/iTunes/iTunesPrefs", "iTunesPrefs"),
    ("iPod_Control/Artwork/ArtworkDB", "ArtworkDB"),
)
ARTWORK_DIR = "iPod_Control/Artwork"
SYNC_PROCESSES = ("iTunes.exe",)          # пишет в базу iPod - должен быть закрыт
HELPER_PROCESSES = ("iTunesHelper.exe",)  # запускает iTunes при подключении iPod
TAG_KEYS = ("title", "artist", "album", "albumartist", "genre", "composer", "comment",
            "grouping", "year", "track_number", "total_tracks", "cd_number", "total_cds",
            "compilation", "sort_title", "sort_artist", "sort_album", "sort_albumartist",
            "sort_composer", "bpm", "rating")
NO_HASH_GENERATIONS = {"FIRST", "SECOND", "THIRD", "FOURTH", "PHOTO", "MINI_1", "MINI_2",
                       "NANO_1", "NANO_2", "VIDEO_1", "VIDEO_2"}

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
warnings.filterwarnings("ignore", message="pygpod: optional dependencies")  # pyusb не нужен


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


# --- устройство -------------------------------------------------------------

def _sysinfo_model(root: Path) -> str:
    sysinfo = root / "iPod_Control" / "Device" / "SysInfo"
    try:
        text = sysinfo.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    line = next((l for l in text.splitlines() if l.lower().startswith("model:")), "")
    return line.split(":", 1)[1].strip() if line else ""


def is_ipod_root(root: Path) -> bool:
    root = Path(root)
    return ((root / "iPod_Control" / "iTunes" / "iTunesDB").is_file()
            and (root / "iPod_Control" / "Music").is_dir())


def check_model(detected, assume_nano2g=False, allow_other=False):
    """(можно_писать, пояснение) для pygpod.Device."""
    generation = detected.generation.name
    if detected.is_shuffle:
        return False, "iPod shuffle не поддерживается (у него другая база - iTunesSD)"
    if detected.sqlite_db:
        return False, f"{detected.model}: база SQLite (nano 5G и новее) не поддерживается"
    if generation == "NANO_2":
        return True, f"Подтверждена модель: {detected.model}"
    if generation == "UNKNOWN":
        if assume_nano2g:
            return True, "Модель не определяется; запись разрешена по подтверждению nano 2G"
        return False, ("Модель iPod не определена. Отметьте «это nano 2G», только если это "
                       "действительно nano 2G")
    if allow_other:
        note = "" if generation in NO_HASH_GENERATIONS else " (база с подписью, нужен корректный SysInfo)"
        return True, f"Модель {detected.model}: запись разрешена как экспериментальная{note}"
    return False, (f"Обнаружен {detected.model}. Проверенная модель - nano 2G; для этой модели "
                   "отметьте «разрешить другие модели (экспериментально)»")


def describe(root) -> dict:
    """Сведения о томе iPod: модель, поколение, обложки, свободное место."""
    root = Path(root)
    info = {"root": root, "model": _sysinfo_model(root) or "iPod (модель неизвестна)",
            "generation": "UNKNOWN", "artwork": False, "status": "", "free": 0}
    try:
        info["free"] = shutil.disk_usage(root).free
    except OSError:
        pass
    try:
        import pygpod
        detected = pygpod.Device.from_mountpoint(str(root))
        info["generation"] = detected.generation.name
        if detected.generation.name != "UNKNOWN":
            info["model"] = detected.model
        info["artwork"] = bool(detected.supports_artwork)
        ok, note = check_model(detected)
        info["status"] = "готов" if ok else note
    except Exception as exc:  # noqa: BLE001 - показать причину в окне
        info["status"] = f"не удалось прочитать: {exc}"
    return info


def find_ipods():
    """iPod ищутся по структуре iPod_Control, а не по метке тома."""
    roots = []
    if sys.platform == "win32":
        import ctypes
        get_drive_type = ctypes.windll.kernel32.GetDriveTypeW
        for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            root = Path(letter + ":\\")
            if get_drive_type(str(root)) in (2, 3) and root.exists() and is_ipod_root(root):
                roots.append(root)
    extra = os.environ.get("MUSICTOOLS_IPOD_ROOT")   # для проверки без устройства
    if extra and is_ipod_root(Path(extra)):
        roots.append(Path(extra))
    return [describe(r) for r in roots]


def _running(names):
    if sys.platform != "win32":
        return ""
    try:
        result = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True,
                                timeout=10, creationflags=_NO_WINDOW)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"Не удалось проверить, закрыт ли iTunes: {exc}") from exc
    if result.returncode:
        raise RuntimeError("Не удалось проверить запущенные процессы iTunes")
    out = result.stdout.decode("utf-8", "replace").lower()
    return next((p for p in names if f'"{p.lower()}"' in out), "")


_EJECT_ERROR = ""


def eject_error() -> str:
    return _EJECT_ERROR


def eject(root) -> bool:
    """Запросить системное извлечение диска через Windows PnP."""
    global _EJECT_ERROR
    _EJECT_ERROR = ""
    if sys.platform != "win32":
        _EJECT_ERROR = "Безопасное системное извлечение доступно только в Windows."
        return False
    _EJECT_ERROR = windows_eject.eject_volume(root) or ""
    return not _EJECT_ERROR


# --- аудио ------------------------------------------------------------------

def collect_audio(source) -> list:
    source = Path(source)
    if source.is_dir():
        return sorted(str(p) for p in source.rglob("*")
                      if p.is_file() and p.suffix.lower() in AUDIO_EXTS)
    if source.is_file():
        return [str(source)]
    return []


_FFMPEG = []


def _ffmpeg():
    """Первый ffmpeg, который действительно запускается: из bin, затем из PATH."""
    if _FFMPEG:
        return _FFMPEG[0]
    names = ("ffmpeg.exe", "ffmpeg") if sys.platform == "win32" else ("ffmpeg",)
    dirs = [APP_DIR / "bin"] + [Path(d) for d in os.environ.get("PATH", "").split(os.pathsep) if d]
    for folder in dirs:
        for name in names:
            exe = folder / name
            if not exe.is_file():
                continue
            try:
                ok = subprocess.run([str(exe), "-version"], capture_output=True, timeout=20,
                                    creationflags=_NO_WINDOW).returncode == 0
            except (OSError, subprocess.SubprocessError):
                ok = False
            if ok:
                _FFMPEG.append(str(exe))
                return str(exe)
            print(f"Пропускаю неработающий ffmpeg: {exe}")
    return None


def _convert(source: Path, dest: Path):
    ffmpeg = _ffmpeg()
    if not ffmpeg:
        raise RuntimeError("Для конвертации нужен ffmpeg из папки bin или переменной PATH")
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_name(dest.stem + ".part.m4a")
    command = [ffmpeg, "-y", "-loglevel", "error", "-i", str(source), "-map", "0:a:0",
               "-map_metadata", "0", "-vn", "-c:a", "aac", "-b:a", "256k", str(temp)]
    result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            timeout=1800, creationflags=_NO_WINDOW)
    if result.returncode or not temp.is_file():
        temp.unlink(missing_ok=True)
        if result.returncode & 0xFFFFFFFF == 0xC0000135:
            raise RuntimeError(f"{ffmpeg} не запускается: рядом нет нужных DLL. Положите в bin "
                               "полную (static/essentials) сборку ffmpeg.exe")
        raise RuntimeError(result.stderr.decode("utf-8", "replace")[-2000:] or "Ошибка ffmpeg")
    os.replace(temp, dest)


def _prepare_audio(source: Path, cache_dir: Path) -> Path:
    if source.suffix.lower() in COMPATIBLE:
        return source
    target = cache_dir / f"{_sha256(source)[:16]}_ipod.m4a"
    if not target.is_file():
        _convert(source, target)
    return target


def _track_fields(source: Path, with_artwork: bool) -> dict:
    """Теги и обложка из ИСХОДНОГО файла (у сконвертированной копии их может не быть)."""
    from pygpod.tags import extract_artwork, read_tags
    try:
        tags = read_tags(str(source))
    except Exception:  # noqa: BLE001 - битые теги не должны мешать передаче
        tags = {}
    fields = {k: tags[k] for k in TAG_KEYS if tags.get(k) not in (None, "", 0)}
    for key in ("title", "artist", "album", "albumartist", "genre", "composer", "comment"):
        if isinstance(fields.get(key), str):
            fields[key] = "".join(ch for ch in fields[key] if ch >= " " or ch == "\t").strip()
            if not fields[key]:
                del fields[key]
    stem = source.stem
    if fields.get("title", stem) == stem and "artist" not in fields and " - " in stem:
        fields["artist"], fields["title"] = (s.strip() for s in stem.split(" - ", 1))
    fields.setdefault("title", stem)
    fields.setdefault("artist", "Unknown Artist")
    fields.setdefault("album", "Unknown Album")
    if not with_artwork:
        fields["cover_art"] = b""
    else:
        try:
            art = extract_artwork(str(source))
        except Exception:  # noqa: BLE001
            art = None
        if art:
            fields["cover_art"] = art
    return fields


# --- резервная копия --------------------------------------------------------

def _backup_files(root: Path):
    files = [(root / rel, name) for rel, name in DEVICE_DATABASES if (root / rel).is_file()]
    art_dir = root / ARTWORK_DIR
    if art_dir.is_dir():
        files += [(p, "Artwork/" + p.name) for p in art_dir.glob("*.ithmb") if p.is_file()]
    return files


def _backup_device_databases(root: Path) -> Path:
    files = _backup_files(root)
    if not any(name == "iTunesDB" for _, name in files):
        raise RuntimeError("На устройстве не найдена iTunesDB; передача отменена")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_dir = root / "iPod_Control" / "iTunes" / "MusicToolsBackups" / stamp
    (backup_dir / "Artwork").mkdir(parents=True, exist_ok=False)
    for source, name in files:
        shutil.copy2(source, backup_dir / name)
    return backup_dir


def _restore_backup_files(backup_dir: Path, root: Path) -> None:
    pairs = [(backup_dir / name, root / rel) for rel, name in DEVICE_DATABASES]
    pairs += [(p, root / ARTWORK_DIR / p.name) for p in (backup_dir / "Artwork").glob("*.ithmb")]
    for backup, target in pairs:
        if not backup.is_file():
            continue
        temp = target.with_name(target.name + f".restore-{os.getpid()}")
        shutil.copy2(backup, temp)
        os.replace(temp, target)


def _ipod_file(root: Path, ipod_path: str) -> Path:
    parts = [part for part in ipod_path.strip(":").split(":") if part]
    return root.joinpath(*parts)


def _remove_copied(root: Path, tracks, why: str) -> None:
    for track in tracks:
        if not track.ipod_path:
            continue
        copied = _ipod_file(root, track.ipod_path)
        try:
            copied.unlink(missing_ok=True)
        except OSError as exc:
            print(f"Не удалось удалить файл {why} {copied}: {exc}")


# --- передача ---------------------------------------------------------------

def _pick_device(device_root):
    if device_root:
        root = Path(device_root)
        if not is_ipod_root(root):
            raise RuntimeError(f"{root}: нет iPod_Control/iTunes/iTunesDB - это не iPod или он не смонтирован")
        return describe(root)
    devices = find_ipods()
    if not devices:
        raise RuntimeError("iPod не найден: смонтированный том должен содержать iPod_Control/iTunes/iTunesDB")
    if len(devices) > 1:
        names = ", ".join(str(d["root"]) for d in devices)
        raise RuntimeError(f"Подключено несколько iPod ({names}) - выберите нужный в списке")
    return devices[0]


def transfer(source_files, device_root=None, assume_nano2g=False, allow_other_models=False,
             with_artwork=True, playlist_name="", eject_after=False):
    """Скопировать аудио и обновить iTunesDB, не запуская и не используя iTunes."""
    import pygpod

    print("Поиск подключённого iPod...")
    device = _pick_device(device_root)
    root = Path(device["root"])
    print(f"Устройство: {device['model']} — {root}")

    running = _running(SYNC_PROCESSES)
    if running:
        raise RuntimeError(f"Закройте {running} перед автономной передачей: он может перезаписать базу iPod")
    if _running(HELPER_PROCESSES):
        print("Внимание: работает iTunesHelper - он может сам запустить iTunes. Если iTunes откроется, "
              "закройте его до конца передачи.")

    incoming = [Path(p) for p in source_files]
    print(f"Файлов для обработки: {len(incoming)}")
    if not incoming:
        raise RuntimeError("Не найдено доступных аудиофайлов")
    missing = [path for path in incoming if not path.is_file()]
    if missing:
        raise RuntimeError(f"Файл не найден: {missing[0]}")

    detected = pygpod.Device.from_mountpoint(str(root))
    ok, note = check_model(detected, assume_nano2g, allow_other_models)
    if not ok:
        raise RuntimeError(note)
    print(note)

    if pygpod.db.transaction.interrupted_commit(str(root)):
        raise RuntimeError("На iPod осталась незавершённая запись базы. Запустите передачу ещё раз "
                           "после проверки iPod или восстановите копию из MusicToolsBackups")

    db = pygpod.Database(str(root), config=pygpod.DatabaseConfig(otg_on_save="keep"),
                         apply_play_counts=False, recover=False)
    if getattr(db, "damage", None):
        raise RuntimeError("iTunesDB повреждена или прочитана не полностью; запись отменена: "
                           + "; ".join(db.damage))
    print(f"Треков на iPod: {len(db.tracks)}")
    artwork = with_artwork and bool(detected.supports_artwork)
    if with_artwork and not artwork:
        print("Эта модель не показывает обложки - они не добавляются.")

    converted_dir = APP_DIR / "ipod_convert_cache"
    converted_dir.mkdir(parents=True, exist_ok=True)
    prepared = []
    for index, source in enumerate(incoming, 1):
        print(f"Подготовка [{index}/{len(incoming)}]: {source.name}")
        try:
            prepared.append((source, _prepare_audio(source, converted_dir)))
        except Exception as exc:  # noqa: BLE001 - один плохой файл не останавливает остальные
            print(f"   пропуск, не удалось подготовить: {exc}")
    if not prepared:
        raise RuntimeError("Ни один файл не удалось подготовить")

    hashes = {}
    sizes = set()
    for _source, path in prepared:
        hashes[path] = _sha256(path)
        sizes.add(path.stat().st_size)

    print("Сверка с треками в базе iPod...")
    existing = {}
    candidates = [t for t in db.tracks if t.file_size in sizes and t.ipod_path]
    for index, track in enumerate(candidates, 1):
        try:
            existing.setdefault(_sha256(_ipod_file(root, track.ipod_path)), track)
        except OSError as exc:
            print(f"Не удалось проверить существующий трек {track.ipod_path}: {exc}")
        if index % 50 == 0:
            print(f"Проверено совпадающих треков: {index}/{len(candidates)}")
    print(f"Совпадающих по размеру треков: {len(candidates)}")

    selected, files_to_add, already = set(), [], []
    for source, path in prepared:
        digest = hashes[path]
        if digest in existing:
            print(f"Уже на iPod: {source.name}")
            already.append(existing[digest])
        elif digest in selected:
            print(f"Повтор в выбранном списке: {source.name}")
        else:
            selected.add(digest)
            files_to_add.append((source, path))

    playlist_missing = []
    if playlist_name:
        playlist = db.get_playlist(playlist_name)
        present = {t.track_id for t in playlist.tracks} if playlist else set()
        playlist_missing = [t for t in already if t.track_id not in present]
    if not files_to_add and not playlist_missing:
        print("Новых треков нет - база iPod не менялась.")
        return 0

    required = sum(path.stat().st_size for _s, path in files_to_add) + 5 * 1024 * 1024
    free = shutil.disk_usage(root).free
    if required > free:
        raise RuntimeError(f"Недостаточно места на iPod: нужно около {required // 2**20} МБ, "
                           f"свободно {free // 2**20} МБ")

    backup_dir = _backup_device_databases(root)
    print(f"Резервная копия базы: {backup_dir}")
    added = []
    try:
        for index, (source, path) in enumerate(files_to_add, 1):
            print(f"Добавление [{index}/{len(files_to_add)}]: {source.name}")
            fields = _track_fields(source, artwork)
            try:
                added.append(db.add_track(str(path), copy=True, **fields))
            except pygpod.ArtworkDBError:
                raise
            except Exception as exc:  # noqa: BLE001
                if "cover_art" not in fields or not fields["cover_art"]:
                    raise
                print(f"   обложку добавить не удалось ({exc}), трек без обложки")
                fields["cover_art"] = b""
                added.append(db.add_track(str(path), copy=True, **fields))
        if playlist_name:
            playlist = db.get_playlist(playlist_name) or db.create_playlist(playlist_name)
            present = {t.track_id for t in playlist.tracks}
            for track in already + added:
                if track.track_id not in present:
                    db.add_track_to_playlist(playlist, track)
                    present.add(track.track_id)
            print(f"Плейлист «{playlist_name}»: треков {len(present)}")
        print("Сохранение iTunesDB...")
        db.save()
    except BaseException:
        try:
            current = pygpod.Database(str(root), apply_play_counts=False, recover=False)
            committed = {track.dbid for track in current.tracks}
        except Exception as exc:  # noqa: BLE001
            print(f"Не удалось определить, завершилась ли запись базы: {exc}")
            print(f"Скопированные файлы не удаляю; резервная копия: {backup_dir}")
            raise
        if not any(track.dbid in committed for track in added):
            _remove_copied(root, added, "после отмены")
        raise

    print("Проверка записанной базы...")
    verified = pygpod.Database(str(root), apply_play_counts=False, recover=False)
    verified_ids = {track.dbid for track in verified.tracks}
    lost = [t for t in added if t.dbid not in verified_ids]
    if lost or getattr(verified, "damage", None):
        _restore_backup_files(backup_dir, root)
        _remove_copied(root, added, "после отката")
        raise RuntimeError(f"Не удалось подтвердить новые записи; база восстановлена из копии {backup_dir}")

    print(f"Передача завершена: добавлено треков {len(added)}, всего на iPod {len(verified.tracks)}")
    if eject_after:
        print("Извлечение iPod...")
        print("iPod извлечён - можно отключать." if eject(root) else
              "Извлечь автоматически не удалось - используйте «Безопасное извлечение устройства».")
    else:
        print("Перед отключением используйте «Безопасное извлечение устройства» в Windows.")
    return len(added)
