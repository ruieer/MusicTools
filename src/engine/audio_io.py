"""Формат и качество скачивания: m4a/mp3 и 128/192/256 кбит/с.

YouTube почти всегда отдаёт родной AAC около 128 кбит/с (иногда выше на
YouTube Music). 192 и 256 для m4a — перекодировка через ffmpeg. MP3 с
YouTube не приходит, его всегда делает ffmpeg из лучшего доступного аудио.
"""
import copy
import subprocess
from pathlib import Path

from mutagen.id3 import APIC, ID3, ID3NoHeaderError
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4Cover

CODECS = ("m4a", "mp3")
BITRATES = (128, 192, 256)
EXTS = (".m4a", ".mp3")
DEFAULT_PRESET = "m4a_128"

_codec = "m4a"
_bitrate = 128


def parse_preset(value) -> tuple[str, int]:
    text = str(value or DEFAULT_PRESET).strip().lower().replace(" ", "_")
    codec, _, rest = text.partition("_")
    try:
        bitrate = int(rest)
    except ValueError:
        codec, bitrate = "m4a", 128
    if codec not in CODECS:
        codec = "m4a"
    if bitrate not in BITRATES:
        bitrate = 128
    return codec, bitrate


def set_preset(value) -> None:
    global _codec, _bitrate
    _codec, _bitrate = parse_preset(value)


def codec() -> str:
    return _codec


def bitrate() -> int:
    return _bitrate


def ext() -> str:
    return f".{_codec}"


def preset_id() -> str:
    return f"{_codec}_{_bitrate}"


def label() -> str:
    return f"{_codec.upper()} {_bitrate}"


def out_path(base: Path) -> Path:
    """Путь к уже скачанному треку (любой формат) или к файлу в текущем формате."""
    found = find_existing(base)
    return found if found else Path(str(base) + ext())


def find_existing(base: Path):
    for suffix in EXTS:
        path = Path(str(base) + suffix)
        if path.exists():
            return path
    return None


def find_downloaded(base: Path) -> Path:
    found = find_existing(base)
    if not found:
        raise FileNotFoundError(f"не появился файл {base.name}{ext()}")
    return found


def is_audio(path: Path) -> bool:
    return path.suffix.lower() in EXTS


def list_audio(folder: Path, recursive=False):
    method = folder.rglob if recursive else folder.glob
    files = []
    for suffix in EXTS:
        files.extend(method(f"*{suffix}"))
    return sorted(files)


def strip_audio_suffix(name: str) -> str:
    lower = name.lower()
    for suffix in EXTS:
        if lower.endswith(suffix):
            return name[: -len(suffix)]
    return name


def _ffmpeg_encode(src: Path, dst: Path, audio_codec: str, kbps: int) -> None:
    encoder = "libmp3lame" if audio_codec == "mp3" else "aac"
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
        "-map", "0:a:0", "-vn", "-map_metadata", "0",
        "-c:a", encoder, "-b:a", f"{kbps}k", str(dst),
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0 or not dst.exists() or dst.stat().st_size < 1000:
        err = (result.stderr or b"").decode("utf-8", "replace").strip()[-300:]
        raise RuntimeError(err or "ffmpeg не смог перекодировать аудио")


def ensure_target(path: Path) -> Path:
    """Приводит скачанный файл к выбранным контейнеру и битрейту."""
    want_codec, want_br = _codec, _bitrate
    want_ext = f".{want_codec}"
    work = path
    if path.suffix.lower() != want_ext:
        tmp = path.with_suffix(want_ext)
        _ffmpeg_encode(path, tmp, want_codec, want_br)
        try:
            path.unlink()
        except OSError:
            pass
        work = tmp
    keep_native = want_codec == "m4a" and want_br == 128
    if keep_native:
        return work
    current = bitrate_kbps(work)
    if abs(current - want_br) <= max(24, want_br * 0.15):
        return work
    tmp = work.with_name(work.stem + ".__q" + work.suffix)
    try:
        _ffmpeg_encode(work, tmp, want_codec, want_br)
        tmp.replace(work)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return work


def ffmpeg_codec_args(path: Path, kbps: int) -> list:
    if path.suffix.lower() == ".mp3":
        return ["-c:a", "libmp3lame", "-b:a", f"{kbps}k"]
    return ["-c:a", "aac", "-b:a", f"{kbps}k"]


def bitrate_kbps(path: Path) -> int:
    default = _bitrate or 128
    try:
        if path.suffix.lower() == ".mp3":
            value = MP3(str(path)).info.bitrate or 0
        else:
            value = MP4(str(path)).info.bitrate or 0
    except Exception:
        value = 0
    kb = round(value / 1000) if value else default
    return max(64, min(320, kb))


def duration(path: Path) -> float:
    try:
        if path.suffix.lower() == ".mp3":
            return float(MP3(str(path)).info.length or 0)
        return float(MP4(str(path)).info.length or 0)
    except Exception:
        return 0


def _mp4_first(tags, key) -> str:
    return str((tags.get(key) or [""])[0] or "").strip()


def _id3_text(tags, frame) -> str:
    items = tags.getall(frame)
    if not items:
        return ""
    text = getattr(items[0], "text", None)
    if not text:
        return ""
    return str(text[0] or "").strip()


def read_fields(path: Path) -> dict:
    """Текстовые теги и флаг обложки — одинаково для m4a и mp3."""
    fields = {"artist": "", "title": "", "album": "", "date": "", "genre": "",
              "album_artist": "", "has_cover": False}
    suffix = path.suffix.lower()
    try:
        if suffix == ".mp3":
            tags = ID3(str(path))
            fields["artist"] = _id3_text(tags, "TPE1")
            fields["title"] = _id3_text(tags, "TIT2")
            fields["album"] = _id3_text(tags, "TALB")
            fields["date"] = _id3_text(tags, "TDRC") or _id3_text(tags, "TYER")
            fields["genre"] = _id3_text(tags, "TCON")
            fields["album_artist"] = _id3_text(tags, "TPE2")
            fields["has_cover"] = bool(tags.getall("APIC"))
        else:
            tags = MP4(str(path)).tags or {}
            fields["artist"] = _mp4_first(tags, "\xa9ART")
            fields["title"] = _mp4_first(tags, "\xa9nam")
            fields["album"] = _mp4_first(tags, "\xa9alb")
            fields["date"] = _mp4_first(tags, "\xa9day")
            fields["genre"] = _mp4_first(tags, "\xa9gen")
            fields["album_artist"] = _mp4_first(tags, "aART")
            fields["has_cover"] = bool(tags.get("covr"))
    except Exception:
        pass
    return fields


def cover_bytes(path: Path):
    try:
        if path.suffix.lower() == ".mp3":
            tags = ID3(str(path))
            frames = tags.getall("APIC")
            return bytes(frames[0].data) if frames else None
        tags = MP4(str(path)).tags or {}
        covers = tags.get("covr") or []
        return bytes(covers[0]) if covers else None
    except Exception:
        return None


def write_cover(path: Path, cover) -> None:
    if not cover:
        return
    mime = "image/png" if cover[:4] == b"\x89PNG" else "image/jpeg"
    if path.suffix.lower() == ".mp3":
        try:
            tags = ID3(str(path))
        except ID3NoHeaderError:
            tags = ID3()
        tags.delall("APIC")
        tags.add(APIC(encoding=3, mime=mime, type=3, desc="Cover", data=cover))
        tags.save(str(path), v2_version=3)
        return
    audio = MP4(str(path))
    if audio.tags is None:
        audio.add_tags()
    fmt = MP4Cover.FORMAT_PNG if mime == "image/png" else MP4Cover.FORMAT_JPEG
    audio.tags["covr"] = [MP4Cover(cover, imageformat=fmt)]
    audio.save()


def copy_tags(old_path: Path, new_path: Path) -> None:
    """Переносит теги. В одном формате — как есть, между mp3 и m4a — общие поля и обложка."""
    if old_path.suffix.lower() == new_path.suffix.lower() == ".m4a":
        old, new = MP4(str(old_path)), MP4(str(new_path))
        if new.tags is None:
            new.add_tags()
        for key in list(new.tags.keys()):
            del new.tags[key]
        for key, value in (old.tags or {}).items():
            new.tags[key] = value
        new.save()
        return
    if old_path.suffix.lower() == new_path.suffix.lower() == ".mp3":
        try:
            old = ID3(str(old_path))
        except ID3NoHeaderError:
            return
        try:
            new = ID3(str(new_path))
        except ID3NoHeaderError:
            new = ID3()
        for key in list(new.keys()):
            del new[key]
        for frame in old.values():
            new.add(copy.copy(frame))
        new.save(str(new_path), v2_version=3)
        return
    fields = read_fields(old_path)
    cover = cover_bytes(old_path)
    tmp = new_path.with_name(new_path.stem + ".__tags" + new_path.suffix)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(new_path),
        "-map", "0", "-c", "copy",
        "-metadata", f"artist={fields['artist']}",
        "-metadata", f"title={fields['title']}",
        "-metadata", f"album={fields['album']}",
        "-metadata", f"album_artist={fields['album_artist']}",
        "-metadata", f"date={fields['date']}",
        "-metadata", f"genre={fields['genre']}",
        str(tmp),
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0 and tmp.exists():
        tmp.replace(new_path)
    elif tmp.exists():
        tmp.unlink()
    write_cover(new_path, cover)
