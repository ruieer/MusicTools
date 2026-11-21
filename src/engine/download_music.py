#!/usr/bin/env python3
"""
Скачивает список "Исполнитель - Название" в m4a или mp3 (качество из настроек).

Установка:   pip install -U yt-dlp rapidfuzz requests mutagen pillow   (+ ffmpeg в PATH)
Запуск:      python download_music.py my_music_list.txt

Результат:
  music/          скачанные .m4a/.mp3 (имя файла = строка из вашего списка)
  report.csv      что нашлось, откуда, с какой оценкой совпадения, откуда теги
  not_found.txt   строки, которые не удалось уверенно найти (для ручного поиска)
  meta_cache.json кэш метаданных (ускоряет повторные запуски)

САМО АУДИО качается только с YouTube/SoundCloud (см. SOURCES) -
Spotify аудиофайлы не отдаёт (DRM), а у Bandcamp в yt-dlp нет поиска.

Источники МЕТАДАННЫХ (в порядке приоритета):
  1. MusicBrainz + Cover Art Archive  (бесплатно, без ключей, хорошие обложки)
  2. Spotify                         (нужен Client ID/Secret или запасной режим)
  3. Deezer                          (без ключей, жанр + обложка)
  4. Bandcamp                        (без ключей, HTML + JSON-LD)
  5. Last.fm                         (API-ключ, отличные жанры/теги)
  6. YouTube                         (теги из самого видео)

Приоритет по полям: MusicBrainz -> Spotify -> Deezer -> Bandcamp -> Last.fm -> YouTube.
Жанры: Last.fm -> Deezer -> остальные (объединяются без повторов).
Обложка: MusicBrainz -> Spotify -> Deezer -> Bandcamp -> превью видео.
Всё приводится к 500x500 JPEG; для превью 16:9 режим задаётся THUMB_MODE.

После скачивания файл проверяется через ffprobe (есть ли аудио и разумная длина).
Метаданные кэшируются в meta_cache.json — повторный запуск не дёргает API зря.

  - Spotify: нужен бесплатный аккаунт разработчика - https://developer.spotify.com/dashboard
    Создайте приложение (Client ID + Client Secret) и задайте переменные
    окружения SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET (или впишите ниже).
    Без них работает запасной режим: поиск через DuckDuckGo + мета-теги
    страницы трека (альбом, год, номер трека, обложка; без жанров).
  - Bandcamp: без ключей, но через разбор HTML поиска и JSON-LD страницы трека.
  - MusicBrainz: без ключей. Обязателен нормальный User-Agent и не более
    1 запроса в секунду (скрипт сам соблюдает).

Скрипт можно прерывать и запускать снова: уже скачанные файлы пропускаются.
"""
import csv
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
import yt_dlp
try:
    from PIL import Image, ImageChops   # pip install pillow
except ImportError:
    Image = ImageChops = None
from rapidfuzz import fuzz
from yt_dlp.utils import sanitize_filename

import audio_io
from core.i18n import tr

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
# Last.fm API key (бесплатно: https://www.last.fm/api/account/create)
# Задаётся в настройках (после вызова core.engine.apply) или переменной окружения LASTFM_API_KEY.
LASTFM_API_KEY = os.environ.get("LASTFM_API_KEY", "")

LIST_FILE = Path(sys.argv[1] if len(sys.argv) > 1 else "my_music_list.txt")


def _music_dir() -> Path:
    """Папка с музыкой: переменная MUSIC_DIR > music_dir.txt рядом со скриптом > ./music.
    Задаётся через set_music_dir.py (пункт 7 в music_tools.bat)."""
    env = os.environ.get("MUSIC_DIR", "").strip().strip('"')
    if env:
        return Path(env)
    try:
        txt = (Path(__file__).resolve().parent / "music_dir.txt").read_text(encoding="utf-8-sig")
        txt = txt.strip().strip('"')
        if txt:
            return Path(txt)
    except OSError:
        pass
    return Path("music")


OUT_DIR = _music_dir()
CACHE_FILE = Path("meta_cache.json")
THRESHOLD = 78          # общий порог уверенности (0-100); выше = строже
REVIEW_MIN = 60         # от этого значения кандидат попадает в "review"
RESULTS_PER_SOURCE = 5  # меньше результатов поиска = быстрее
SLEEP = 0.6             # пауза между треками (0.5–1.0; меньше → быстрее, но риск 403)
MIN_DUR, MAX_DUR = 45, 15 * 60
THUMB_SIZE = 500        # размер обложки
# Сначала срезаются однотонные полосы по краям (если TRIM_BARS), потом:
# "squish" - растянуть картинку до квадрата (без обрезки, но с искажением)
# "crop"   - обрезать по центру в квадрат (без искажения, но теряются края)
THUMB_MODE = "squish"
TRIM_BARS = True        # срезать однотонные полосы по бокам/сверху/снизу
BAR_TOL = 28            # допуск по цвету полос (JPEG-шум); больше = агрессивнее
META_TITLE_MIN = 80     # порог совпадения названия для Spotify/Bandcamp/MusicBrainz
META_ARTIST_MIN = 75    # порог совпадения исполнителя
MAX_GENRES = 1
HTTP_TIMEOUT = 5        # короче таймаут — не висим на мёртвых API
USE_SPOTIFY_KEYLESS = False  # True = Spotify без ключей (через DuckDuckGo): медленно, но даёт альбом/год
USE_BANDCAMP = False         # True = Bandcamp, если не хватает альбома/жанра/обложки: медленно, но лучший источник для андерграунда
MAX_FILENAME_LEN = 120  # iPod nano лучше себя чувствует с умеренной длиной имени
# Сколько потоков на метаданные (Last.fm/Deezer/Spotify/MB параллельно)
META_WORKERS = 4
UA = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

# MusicBrainz требует осмысленный User-Agent + не более 1 req/sec
MB_UA = {
    "User-Agent": "download_music.py/1.2 (personal music downloader; contact: local-user)",
    "Accept": "application/json",
}
_mb_last_request = 0.0

# Порядок важен: сначала YouTube, потом SoundCloud
SOURCES = [("ytsearch", "YouTube"), ("scsearch", "SoundCloud")]

BAD_WORDS = {
    "live", "cover", "karaoke", "remix", "slowed", "reverb", "nightcore",
    "sped", "instrumental", "кавер", "ремикс", "караоке", "концерт", "минус",
}


def norm(s: str) -> str:
    s = (s or "").lower().replace("ё", "е")
    return re.sub(r"[^\w]+", " ", s).strip()


def split_line(line: str):
    if " - " in line:
        a, t = line.split(" - ", 1)
        return a.strip(), t.strip()
    return "", line.strip()


def safe_filename(line: str) -> str:
    """Имя файла, безопасное для iPod nano и большинства ФС."""
    name = sanitize_filename(line, restricted=False)
    # убираем символы, с которыми iPod/ФС иногда сбоят (знаки ? оставляем)
    name = re.sub(r'[\\/:*"<>|]+', " ", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if len(name) > MAX_FILENAME_LEN:
        name = name[:MAX_FILENAME_LEN].rstrip(" .")
    return name or "track"


def score(entry, artist, title):
    """Возвращает (итоговая оценка, оценка названия, оценка исполнителя) или None."""
    dur = entry.get("duration")
    if dur and not (MIN_DUR <= dur <= MAX_DUR):
        return None

    q_artist, q_title = norm(artist), norm(title)
    c_title = norm(entry.get("title"))
    c_chan = norm(entry.get("channel") or entry.get("uploader"))

    c_title_clean = c_title.replace(q_artist, " ").strip() if q_artist else c_title

    title_score = fuzz.token_sort_ratio(q_title, c_title_clean)
    if len(q_title) >= 8:
        title_score = max(title_score, 0.95 * fuzz.partial_ratio(q_title, c_title_clean))

    if q_artist:
        artist_score = max(
            fuzz.partial_ratio(q_artist, c_title) if len(q_artist) >= 4
            else (100 if q_artist in c_title.split() else 0),
            fuzz.partial_ratio(q_artist, c_chan) if len(q_artist) >= 4
            else (100 if q_artist in c_chan.split() else 0),
        )
    else:
        artist_score = 100

    total = 0.6 * title_score + 0.4 * artist_score

    q_words = set(norm(artist + " " + title).split())
    c_words = set(c_title.split())
    if (BAD_WORDS & c_words) - q_words:
        total -= 25

    if "topic" in c_chan or "official audio" in c_title:
        total += 5

    return total, title_score, artist_score


def find_best(searcher, line, artist, title):
    query = f"{artist} {title}".strip()
    best_accept, best_any = None, None
    for prefix, label in SOURCES:
        try:
            info = searcher.extract_info(
                f"{prefix}{RESULTS_PER_SOURCE}:{query}", download=False
            )
        except Exception:
            continue
        for e in (info or {}).get("entries") or []:
            if not e:
                continue
            url = e.get("webpage_url") or e.get("url")
            if not url:
                continue
            s = score(e, artist, title)
            if s is None:
                continue
            total, t_sc, a_sc = s
            cand = (total, label, e.get("title"), url)
            if best_any is None or total > best_any[0]:
                best_any = cand
            if t_sc >= 75 and a_sc >= 70 and total >= THRESHOLD:
                if best_accept is None or total > best_accept[0]:
                    best_accept = cand
        if best_accept:
            break
    return best_accept, best_any


def trim_bars(img):
    """Срезает однотонные полосы по краям. Если все 4 угла одного цвета -
    считаем это фоном и обрезаем по границе остального содержимого."""
    w, h = img.size
    px = img.load()
    corners = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
    bg = corners[0]
    if any(max(abs(a - b) for a, b in zip(c, bg)) > BAR_TOL for c in corners):
        return img
    diff = ImageChops.difference(img, Image.new("RGB", img.size, bg)).convert("L")
    bbox = diff.point(lambda p: 255 if p > BAR_TOL else 0).getbbox()
    if not bbox:
        return img
    l, t, r, b = bbox
    if (r - l) * (b - t) < 0.08 * w * h or (r - l) < 32 or (b - t) < 32:
        return img                      # срезали бы почти всё - не трогаем
    inset = 2 if (r - l) > 100 and (b - t) > 100 else 0   # убрать размытый край
    return img.crop((l + inset, t + inset, r - inset, b - inset))


def finish_cover(img) -> bytes:
    """PIL-картинка -> квадратный JPEG THUMB_SIZE x THUMB_SIZE (bytes)."""
    if THUMB_MODE == "crop":
        s = min(img.size)
        left, top = (img.width - s) // 2, (img.height - s) // 2
        img = img.crop((left, top, left + s, top + s))
    img = img.resize((THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def make_cover_jpg(path: str):
    """Любую картинку (webp/png/jpg) -> JPEG ровно THUMB_SIZE x THUMB_SIZE.
    Возвращает bytes или None."""
    if Image is not None:
        try:
            img = Image.open(path).convert("RGB")
            if TRIM_BARS:
                img = trim_bars(img)
            return finish_cover(img)
        except Exception as ex:
            print(tr("  Pillow не справился, пробую ffmpeg:"), ex)
    size = THUMB_SIZE
    if THUMB_MODE == "crop":
        vf = f"crop='min(iw,ih)':'min(iw,ih)',scale={size}:{size}"
    else:
        vf = f"scale={size}:{size}"
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "cover.jpg")
        try:
            r = subprocess.run(
                ["ffmpeg", "-y", "-i", path, "-frames:v", "1", "-vf", vf, "-q:v", "2", out],
                capture_output=True)
        except FileNotFoundError:
            print(tr("  ffmpeg не найден в PATH - обложка не обработана"))
            return None
        if r.returncode != 0 or not os.path.exists(out):
            print(tr("  ffmpeg не смог обработать обложку:"),
                  r.stderr.decode("utf-8", "ignore").strip().splitlines()[-1:])
            return None
        with open(out, "rb") as f:
            return f.read()


def pop_thumbnail(base_path: Path):
    """Находит скачанное превью рядом с треком, делает из него 500x500 JPEG
    и удаляет файл превью. Возвращает bytes или None."""
    cover = None
    for ext in (".webp", ".jpg", ".jpeg", ".png"):
        th = Path(str(base_path) + ext)
        if th.exists():
            if cover is None:
                cover = make_cover_jpg(str(th))
            try:
                th.unlink()
            except OSError:
                pass
    return cover


def check_audio_ok(path: Path) -> bool:
    """Проверяет, что файл существует, не пустой и содержит аудио разумной длины."""
    if not path.exists() or path.stat().st_size < 50_000:
        return False
    try:
        r = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            return False
        dur = float(r.stdout.strip() or 0)
        return MIN_DUR <= dur <= MAX_DUR
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Кэш метаданных
# ---------------------------------------------------------------------------

def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_cache(cache: dict):
    try:
        CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as ex:
        print(tr("  не удалось сохранить кэш:"), ex)


def cache_key(artist: str, title: str) -> str:
    return f"{norm(artist)}|{norm(title)}"


# ---------------------------------------------------------------------------
# Метаданные: YouTube (из самого видео)
# ---------------------------------------------------------------------------

def fetch_tags(url):
    """Альбом/жанр/год/номер трека из самого видео, если источник их отдаёт."""
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return {}

    tags = {}
    if info.get("album"):
        tags["album"] = info["album"]
    if info.get("genre"):
        tags["genres"] = [g.strip() for g in re.split(r"[;,]", info["genre"]) if g.strip()]
    if isinstance(info.get("track_number"), int):
        tags["track"] = info["track_number"]
    year = info.get("release_year") or (info.get("upload_date") or "")[:4]
    if year:
        tags["date"] = str(year)
    return tags


# ---------------------------------------------------------------------------
# Метаданные: Spotify
# ---------------------------------------------------------------------------

_spotify_token = {"value": None, "expires": 0.0}


def _spotify_get_token():
    if not (SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET):
        return None
    if _spotify_token["value"] and time.time() < _spotify_token["expires"] - 30:
        return _spotify_token["value"]
    try:
        r = requests.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET),
            timeout=HTTP_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None
    _spotify_token["value"] = data.get("access_token")
    _spotify_token["expires"] = time.time() + data.get("expires_in", 3600)
    return _spotify_token["value"]


def _match_ok(q_artist, q_title, c_artists, c_title):
    """Проверка совпадения для Spotify/Bandcamp/MusicBrainz. c_artists - список строк."""
    t_sc = fuzz.token_sort_ratio(norm(q_title), norm(c_title))
    if q_artist:
        qa = norm(q_artist)
        a_sc = max((max(fuzz.ratio(qa, norm(a)), fuzz.partial_ratio(qa, norm(a))
                        if len(qa) >= 4 else 0) for a in c_artists), default=0)
    else:
        a_sc = 100
    ok = t_sc >= META_TITLE_MIN and a_sc >= META_ARTIST_MIN
    return ok, 0.6 * t_sc + 0.4 * a_sc


def spotify_lookup(artist, title):
    """Возвращает словарь метаданных + 'cover_url' или None."""
    token = _spotify_get_token()
    if not token:
        return spotify_lookup_keyless(artist, title)
    headers = {"Authorization": f"Bearer {token}"}
    q = f'track:"{title}" artist:"{artist}"' if artist else f'track:"{title}"'
    try:
        r = requests.get(
            "https://api.spotify.com/v1/search",
            params={"q": q, "type": "track", "limit": 5},
            headers=headers, timeout=HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return None
        items = r.json().get("tracks", {}).get("items", [])
    except Exception:
        return None

    best, best_sc = None, -1
    for it in items:
        ok, sc = _match_ok(artist, title, [a["name"] for a in it.get("artists", [])], it.get("name"))
        if ok and sc > best_sc:
            best, best_sc = it, sc
    if not best:
        return None

    album = best.get("album") or {}
    meta = {"album": album.get("name")}
    if album.get("artists"):
        meta["album_artist"] = ", ".join(a["name"] for a in album["artists"])
    m = re.match(r"(\d{4})", album.get("release_date") or "")
    if m:
        meta["date"] = m.group(1)
    if best.get("track_number"):
        meta["track"] = best["track_number"]
    if album.get("total_tracks"):
        meta["track_total"] = album["total_tracks"]
    if best.get("disc_number"):
        meta["disc"] = best["disc_number"]
    imgs = album.get("images") or []
    if imgs:
        meta["cover_url"] = max(imgs, key=lambda i: i.get("width") or 0)["url"]

    genres = []
    try:
        aid = best["artists"][0]["id"]
        ra = requests.get(f"https://api.spotify.com/v1/artists/{aid}",
                          headers=headers, timeout=HTTP_TIMEOUT)
        if ra.status_code == 200:
            genres = ra.json().get("genres") or []
    except Exception:
        pass
    if genres:
        meta["genres"] = genres
    return meta


def _og(page, prop):
    """Достаёт content из <meta property|name="prop" content="...">."""
    import html as _html
    m = (re.search(r'<meta[^>]+(?:property|name)="%s"[^>]+content="([^"]*)"' % re.escape(prop), page)
         or re.search(r'<meta[^>]+content="([^"]*)"[^>]+(?:property|name)="%s"' % re.escape(prop), page))
    return _html.unescape(m.group(1)).strip() if m else ""


def spotify_lookup_keyless(artist, title):
    """Spotify БЕЗ ключей: ищем ссылку на трек через DuckDuckGo и читаем
    мета-теги публичной страницы open.spotify.com."""
    q = f"site:open.spotify.com/track {artist} {title}".strip()
    try:
        r = requests.post("https://html.duckduckgo.com/html/", data={"q": q},
                          headers=UA, timeout=HTTP_TIMEOUT)
        if r.status_code != 200:
            return None
    except Exception:
        return None

    ids = []
    for tid in re.findall(
            r"open\.spotify\.com(?:%2F|/)(?:intl-\w+(?:%2F|/))?track(?:%2F|/)([A-Za-z0-9]{22})", r.text):
        if tid not in ids:
            ids.append(tid)

    best, best_sc = None, -1
    for tid in ids[:4]:
        try:
            pr = requests.get(f"https://open.spotify.com/track/{tid}", headers=UA, timeout=HTTP_TIMEOUT)
            if pr.status_code != 200:
                continue
            page = pr.text
        except Exception:
            continue
        c_title = _og(page, "og:title")
        parts = [x.strip() for x in _og(page, "og:description").split("\u00b7")]
        c_artist = parts[0] if parts else ""
        if not c_title:
            continue
        ok, sc = _match_ok(artist, title, [c_artist], c_title)
        if ok and sc > best_sc:
            best, best_sc = (page, parts), sc
    if not best:
        return None

    page, parts = best
    meta = {}
    date = _og(page, "music:release_date")
    m = re.match(r"(\d{4})", date) or (re.match(r"(\d{4})$", parts[-1]) if parts else None)
    if m:
        meta["date"] = m.group(1)
    tn = _og(page, "music:album:track")
    if tn.isdigit():
        meta["track"] = int(tn)
    if _og(page, "og:image"):
        meta["cover_url"] = _og(page, "og:image")

    album_url = _og(page, "music:album")
    if album_url.startswith("http"):
        try:
            ar = requests.get(album_url, headers=UA, timeout=HTTP_TIMEOUT)
            if ar.status_code == 200:
                name = _og(ar.text, "og:title")
                if name:
                    meta["album"] = name
        except Exception:
            pass
    return meta or None


# ---------------------------------------------------------------------------
# Метаданные: Bandcamp
# ---------------------------------------------------------------------------

def _strip_tags(s):
    import html as _html
    return _html.unescape(re.sub(r"<[^>]+>", " ", s or "")).strip()


def bandcamp_lookup(artist, title):
    """Поиск трека на Bandcamp через HTML поиска + JSON-LD страницы трека."""
    query = f"{artist} {title}".strip()
    try:
        r = requests.get("https://bandcamp.com/search",
                         params={"q": query, "item_type": "t"},
                         headers=UA, timeout=HTTP_TIMEOUT)
        if r.status_code != 200:
            return None
        page = r.text
    except Exception:
        return None

    blocks = re.findall(r'<li class="searchresult.*?</li>', page, re.S)[:5]
    best_url, best_sc = None, -1
    for b in blocks:
        mh = re.search(r'<div class="heading">\s*<a href="([^"]+)"[^>]*>(.*?)</a>', b, re.S)
        if not mh:
            continue
        url = mh.group(1).split("?")[0]
        c_title = _strip_tags(mh.group(2))
        ms = re.search(r'<div class="subhead">(.*?)</div>', b, re.S)
        sub = _strip_tags(ms.group(1)) if ms else ""
        mb = re.search(r"\bby\s+(.+)$", sub)
        c_artist = mb.group(1).strip() if mb else sub
        ok, sc = _match_ok(artist, title, [c_artist], c_title)
        if ok and sc > best_sc:
            best_url, best_sc = url, sc
    if not best_url:
        return None

    try:
        rp = requests.get(best_url, headers=UA, timeout=HTTP_TIMEOUT)
        rp.raise_for_status()
        mj = re.search(r'<script type="application/ld\+json">(.*?)</script>', rp.text, re.S)
        ld = json.loads(mj.group(1)) if mj else {}
    except Exception:
        return None

    meta = {}
    album = ld.get("inAlbum") or {}
    if album.get("name"):
        meta["album"] = album["name"]
    by = ld.get("byArtist") or {}
    if isinstance(by, dict) and by.get("name"):
        meta["album_artist"] = by["name"]
    my = re.search(r"(\d{4})", ld.get("datePublished") or "")
    if my:
        meta["date"] = my.group(1)
    if isinstance(ld.get("position"), int):
        meta["track"] = ld["position"]
    kw = ld.get("keywords")
    if isinstance(kw, str):
        kw = [k.strip() for k in kw.split(",")]
    if kw:
        meta["genres"] = [k for k in kw if k]
    img = ld.get("image")
    if isinstance(img, list):
        img = img[0] if img else None
    if img:
        meta["cover_url"] = img
    return meta or None


# ---------------------------------------------------------------------------
# Метаданные: Last.fm (в основном жанры/теги)
# ---------------------------------------------------------------------------

def lastfm_lookup(artist, title):
    """Жанры/теги из Last.fm. Возвращает dict с genres или None."""
    if not LASTFM_API_KEY:
        return None
    try:
        r = requests.get(
            "https://ws.audioscrobbler.com/2.0/",
            params={
                "method": "track.getInfo",
                "api_key": LASTFM_API_KEY,
                "artist": artist,
                "track": title,
                "autocorrect": 1,
                "format": "json",
            },
            headers=UA,
            timeout=HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return None
        data = r.json()
    except Exception:
        return None

    track = data.get("track") or {}
    if not track:
        return None

    # проверяем совпадение названия
    c_title = track.get("name") or ""
    c_artist = (track.get("artist") or {}).get("name") or ""
    ok, _ = _match_ok(artist, title, [c_artist] if c_artist else [], c_title)
    if not ok and artist and title:
        # иногда autocorrect сильно меняет — всё равно берём теги, если artist похож
        if fuzz.partial_ratio(norm(artist), norm(c_artist)) < 70:
            return None

    meta = {}
    tags = (track.get("toptags") or {}).get("tag") or []
    if isinstance(tags, dict):
        tags = [tags]
    genres = []
    for t in tags:
        name = (t.get("name") or "").strip()
        if name and name.lower() not in ("seen live", "favorites", "favourite", "awesome"):
            genres.append(name)
    if not genres and artist:
        try:
            r2 = requests.get(
                "https://ws.audioscrobbler.com/2.0/",
                params={
                    "method": "artist.getTopTags",
                    "api_key": LASTFM_API_KEY,
                    "artist": artist,
                    "autocorrect": 1,
                    "format": "json",
                },
                headers=UA,
                timeout=HTTP_TIMEOUT,
            )
            if r2.status_code == 200:
                tags2 = ((r2.json().get("toptags") or {}).get("tag")) or []
                if isinstance(tags2, dict):
                    tags2 = [tags2]
                for t in tags2:
                    name = (t.get("name") or "").strip()
                    if name and name.lower() not in ("seen live", "favorites", "favourite", "awesome"):
                        genres.append(name)
                    if len(genres) >= MAX_GENRES:
                        break
        except Exception:
            pass
    if genres:
        meta["genres"] = genres[:MAX_GENRES]

    # год иногда есть в wiki/album
    album = track.get("album") or {}
    if album.get("title"):
        meta["album"] = album["title"]

    return meta or None


# ---------------------------------------------------------------------------
# Метаданные: Deezer (жанр + иногда альбом/обложка)
# ---------------------------------------------------------------------------

def deezer_lookup(artist, title):
    """Поиск в Deezer. Жанр, альбом, обложка."""
    q = f'artist:"{artist}" track:"{title}"' if artist else f'track:"{title}"'
    try:
        r = requests.get(
            "https://api.deezer.com/search",
            params={"q": q, "limit": 5},
            headers=UA,
            timeout=HTTP_TIMEOUT,
        )
        if r.status_code != 200:
            return None
        items = r.json().get("data") or []
    except Exception:
        return None

    best, best_sc = None, -1
    for it in items:
        c_title = it.get("title") or ""
        c_artist = (it.get("artist") or {}).get("name") or ""
        ok, sc = _match_ok(artist, title, [c_artist] if c_artist else [], c_title)
        if ok and sc > best_sc:
            best, best_sc = it, sc
    if not best:
        try:
            r = requests.get(
                "https://api.deezer.com/search",
                params={"q": f"{artist} {title}".strip(), "limit": 5},
                headers=UA,
                timeout=HTTP_TIMEOUT,
            )
            items = r.json().get("data") or [] if r.status_code == 200 else []
        except Exception:
            items = []
        for it in items:
            c_title = it.get("title") or ""
            c_artist = (it.get("artist") or {}).get("name") or ""
            ok, sc = _match_ok(artist, title, [c_artist] if c_artist else [], c_title)
            if ok and sc > best_sc:
                best, best_sc = it, sc
    if not best:
        return None

    meta = {}
    album = best.get("album") or {}
    if album.get("title"):
        meta["album"] = album["title"]
    if album.get("cover_xl") or album.get("cover_big") or album.get("cover_medium"):
        meta["cover_url"] = (
            album.get("cover_xl")
            or album.get("cover_big")
            or album.get("cover_medium")
        )

    # жанр у Deezer часто на уровне album → нужно доп. запрос, но можно взять из artist
    # у search-результата жанра нет напрямую — попробуем album id
    album_id = album.get("id")
    if album_id:
        try:
            ar = requests.get(
                f"https://api.deezer.com/album/{album_id}",
                headers=UA,
                timeout=HTTP_TIMEOUT,
            )
            if ar.status_code == 200:
                adata = ar.json()
                genres = []
                for g in (adata.get("genres") or {}).get("data") or []:
                    name = (g.get("name") or "").strip()
                    if name:
                        genres.append(name)
                if genres:
                    meta["genres"] = genres[:MAX_GENRES]
                if not meta.get("date"):
                    rd = adata.get("release_date") or ""
                    m = re.match(r"(\d{4})", rd)
                    if m:
                        meta["date"] = m.group(1)
                if adata.get("title") and not meta.get("album"):
                    meta["album"] = adata["title"]
        except Exception:
            pass

    return meta or None


# ---------------------------------------------------------------------------
# Метаданные: MusicBrainz + Cover Art Archive
# ---------------------------------------------------------------------------

def _mb_request(url, params=None):
    """Запрос к MusicBrainz с соблюдением 1 req/sec и правильным User-Agent."""
    global _mb_last_request
    now = time.time()
    wait = 1.05 - (now - _mb_last_request)
    if wait > 0:
        time.sleep(wait)
    try:
        r = requests.get(url, params=params, headers=MB_UA, timeout=HTTP_TIMEOUT)
        _mb_last_request = time.time()
        if r.status_code == 503:
            time.sleep(2.0)
            r = requests.get(url, params=params, headers=MB_UA, timeout=HTTP_TIMEOUT)
            _mb_last_request = time.time()
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None


def musicbrainz_lookup(artist, title):
    """Поиск записи в MusicBrainz. Возвращает meta + cover_url или None."""
    if artist:
        q = f'recording:"{title}" AND artist:"{artist}"'
    else:
        q = f'recording:"{title}"'

    data = _mb_request(
        "https://musicbrainz.org/ws/2/recording",
        params={"query": q, "fmt": "json", "limit": 8},
    )
    if not data:
        return None

    recordings = data.get("recordings") or []
    best, best_sc = None, -1

    for rec in recordings:
        c_title = rec.get("title") or ""
        credits = rec.get("artist-credit") or []
        c_artists = []
        for c in credits:
            if isinstance(c, dict):
                name = c.get("name") or (c.get("artist") or {}).get("name")
                if name:
                    c_artists.append(name)
        if not c_artists:
            continue

        ok, sc = _match_ok(artist, title, c_artists, c_title)
        if not ok:
            continue

        releases = rec.get("releases") or []
        if not releases:
            rid = rec.get("id")
            if rid:
                detail = _mb_request(
                    f"https://musicbrainz.org/ws/2/recording/{rid}",
                    params={"fmt": "json", "inc": "releases+artists"},
                )
                if detail:
                    releases = detail.get("releases") or []
                    rec = detail

        if ok and sc > best_sc:
            best, best_sc = (rec, releases), sc

    if not best:
        return None

    rec, releases = best
    # теги (жанры) поиск не отдаёт — нужен отдельный lookup
    rid = rec.get("id")
    if rid and not rec.get("tags"):
        detail = _mb_request(
            f"https://musicbrainz.org/ws/2/recording/{rid}",
            params={"fmt": "json", "inc": "tags+artists+releases"},
        )
        if detail:
            if not releases:
                releases = detail.get("releases") or []
            rec = detail
    meta = {}

    chosen_release = None
    for rel in releases:
        status = (rel.get("status") or "").lower()
        if status in ("official", "") or chosen_release is None:
            chosen_release = rel
            if status == "official":
                break

    if chosen_release:
        if chosen_release.get("title"):
            meta["album"] = chosen_release["title"]
        date = chosen_release.get("date") or ""
        m = re.match(r"(\d{4})", date)
        if m:
            meta["date"] = m.group(1)
        media = chosen_release.get("media") or []
        for medium in media:
            for track in medium.get("tracks") or []:
                if track.get("recording", {}).get("id") == rec.get("id"):
                    num = track.get("number")
                    if num and str(num).isdigit():
                        meta["track"] = int(num)
                    break

        release_mbid = chosen_release.get("id")
        if release_mbid:
            cover_url = f"https://coverartarchive.org/release/{release_mbid}/front-500"
            try:
                hr = requests.head(cover_url, headers=MB_UA, timeout=HTTP_TIMEOUT, allow_redirects=True)
                if hr.status_code == 200:
                    meta["cover_url"] = cover_url
            except Exception:
                pass

    credits = rec.get("artist-credit") or []
    names = []
    for c in credits:
        if isinstance(c, dict):
            name = c.get("name") or (c.get("artist") or {}).get("name")
            if name:
                names.append(name)
    if names:
        meta["album_artist"] = ", ".join(names)

    tags = rec.get("tags") or []
    if tags:
        tags = sorted(tags, key=lambda t: t.get("count", 0), reverse=True)
        genres = [t["name"] for t in tags if t.get("name")]
        if genres:
            meta["genres"] = genres[:MAX_GENRES]

    return meta or None


# ---------------------------------------------------------------------------
# Сборка метаданных, обложка, запись тегов
# ---------------------------------------------------------------------------

def download_square_cover(url):
    """Скачивает обложку по ссылке и приводит к THUMB_SIZE x THUMB_SIZE."""
    try:
        r = requests.get(url, headers=UA, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
    except Exception:
        return None
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "cover_src")
        with open(p, "wb") as f:
            f.write(r.content)
        return make_cover_jpg(p) or r.content


def _merge_meta(sources_ordered, genre_order):
    """Склеивает поля и жанры из списка (name, src)."""
    meta, used = {}, []
    for key_name in ("album", "album_artist", "date", "track", "track_total", "disc"):
        for name, src in sources_ordered:
            if src and src.get(key_name):
                meta[key_name] = src[key_name]
                if name not in used:
                    used.append(name)
                break
    genres, seen = [], set()
    for name, src in genre_order:
        for g in (src or {}).get("genres", []):
            if g.lower() not in seen:
                seen.add(g.lower())
                genres.append(g)
                if name not in used:
                    used.append(name)
    if genres:
        meta["genres"] = genres[:MAX_GENRES]
    return meta, used


def collect_metadata(artist, title, url, cache: dict):
    """Собирает теги. Быстрые API параллельно; Bandcamp — только если не хватает данных."""
    key = cache_key(artist, title)
    cached = cache.get(key)

    if cached and isinstance(cached, dict) and cached.get("_v") == 3:
        meta = {k: v for k, v in cached.items() if k not in ("_used", "cover_url", "_v")}
        used = list(cached.get("_used") or [])
        cover = None
        cover_url = cached.get("cover_url")
        if cover_url:
            cover = download_square_cover(cover_url)
        return meta, cover, used

    # 1) быстрые источники параллельно (Bandcamp HTML — самый медленный, позже)
    jobs = {
        "Last.fm": lambda: lastfm_lookup(artist, title),
        "Deezer": lambda: deezer_lookup(artist, title),
        "MusicBrainz": lambda: musicbrainz_lookup(artist, title),
    }
    # Spotify без ключей (через DuckDuckGo) очень медленный и редко находит
    # андерграунд - включаем его только если заданы SPOTIFY_CLIENT_ID/SECRET.
    if (SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET) or USE_SPOTIFY_KEYLESS:
        jobs["Spotify"] = lambda: spotify_lookup(artist, title)
    if url:
        jobs["YouTube"] = lambda: fetch_tags(url)

    results = {}
    with ThreadPoolExecutor(max_workers=META_WORKERS) as pool:
        futs = {pool.submit(fn): name for name, fn in jobs.items()}
        for fut in futs:
            name = futs[fut]
            try:
                results[name] = fut.result()
            except Exception:
                results[name] = None

    lf = results.get("Last.fm")
    dz = results.get("Deezer")
    sp = results.get("Spotify")
    mb = results.get("MusicBrainz")
    yt = results.get("YouTube")
    bc = None

    ordered = [
        ("MusicBrainz", mb),
        ("Spotify", sp),
        ("Deezer", dz),
        ("Last.fm", lf),
        ("YouTube", yt),
    ]
    genre_order = [
        ("Last.fm", lf),
        ("Deezer", dz),
        ("MusicBrainz", mb),
        ("Spotify", sp),
        ("YouTube", yt),
    ]
    meta, used = _merge_meta(ordered, genre_order)

    need_album = not meta.get("album")
    need_genre = not meta.get("genres")
    need_cover = not any(
        (src or {}).get("cover_url") for src in (mb, sp, dz)
    )
    # Bandcamp только если реально чего-то не хватает
    if USE_BANDCAMP and (need_album or need_genre or need_cover):
        bc = bandcamp_lookup(artist, title)
        if bc:
            ordered.insert(3, ("Bandcamp", bc))
            genre_order.insert(4, ("Bandcamp", bc))
            meta, used = _merge_meta(ordered, genre_order)

    cover = None
    cover_url = None
    for name, src in (("MusicBrainz", mb), ("Spotify", sp), ("Deezer", dz), ("Bandcamp", bc)):
        if src and src.get("cover_url"):
            cover_url = src["cover_url"]
            cover = download_square_cover(cover_url)
            if cover:
                if name not in used:
                    used.append(name)
                break

    to_cache = dict(meta)
    to_cache["_used"] = used
    to_cache["_v"] = 3
    if cover_url:
        to_cache["cover_url"] = cover_url
    cache[key] = to_cache

    return meta, cover, used


# Если альбом не найден или это сингл - в поле "альбом" пишем название песни + "(single)"
SINGLE_FMT = "{title}(single)"      # например: Жгу Лёгкие(single)


def _looks_like_single(album: str, title: str) -> bool:
    """Альбом совпадает с названием трека (с пометкой single или без) - это сингл."""
    a = re.sub(r"[\(\[]\s*single\s*[\)\]]|\s-\s*single\s*$", "", album or "", flags=re.I)
    return bool(norm(a)) and norm(a) == norm(title)


def _existing_album(path: Path) -> str:
    return audio_io.read_fields(path).get("album") or ""


def resolve_album(path: Path, meta, title: str) -> str:
    """Какой альбом записать. '' = не трогать поле."""
    title = (title or "").strip()
    album = str((meta or {}).get("album") or "").strip()
    if not title:
        return album
    if not album:
        existing = _existing_album(path)       # настоящий альбом из файла не затираем
        if not existing or _looks_like_single(existing, title):
            return SINGLE_FMT.format(title=title)
        return ""
    if _looks_like_single(album, title):
        return SINGLE_FMT.format(title=title)
    return album


def _ffmpeg_text_tags(path: Path, meta, artist: str, title: str):
    """Пишет текстовые теги через ffmpeg (так же, как artist — его Mp3tag видит)."""
    meta = meta or {}
    album_artist = (meta.get("album_artist") or "")
    if not isinstance(album_artist, str):
        album_artist = str(album_artist)
    album_artist = album_artist.strip() or artist
    genres = meta.get("genres") or []
    if isinstance(genres, str):
        genre = genres.strip()
    else:
        genre = ", ".join(str(g).strip() for g in genres if str(g).strip())

    tmp = path.with_name(path.stem + ".__retag" + path.suffix)
    cmd = [
        "ffmpeg", "-y", "-i", str(path),
        "-map", "0", "-c", "copy",
        "-metadata", f"artist={artist or ''}",
        "-metadata", f"title={title or ''}",
        "-metadata", f"album_artist={album_artist}",
    ]
    album = resolve_album(path, meta, title)
    if album:
        cmd += ["-metadata", f"album={album}"]
    if meta.get("date"):
        cmd += ["-metadata", f"date={str(meta['date'])}"]
    if genre:
        cmd += ["-metadata", f"genre={genre}"]
    if meta.get("track"):
        tr = str(int(meta["track"]))
        total = int(meta.get("track_total") or 0)
        if total:
            tr = f"{tr}/{total}"
        cmd += ["-metadata", f"track={tr}"]
    if meta.get("disc"):
        cmd += ["-metadata", f"disc={int(meta['disc'])}"]
    cmd.append(str(tmp))
    try:
        r = subprocess.run(cmd, capture_output=True)
    except FileNotFoundError:
        print(tr("  ffmpeg не найден — текстовые теги не записаны"))
        return
    if r.returncode != 0 or not tmp.exists() or tmp.stat().st_size < 1000:
        err = r.stderr.decode("utf-8", "ignore").strip().splitlines()
        print(tr("  ffmpeg не записал теги:"), err[-1:] if err else r.returncode)
        if tmp.exists():
            tmp.unlink()
        return
    tmp.replace(path)


def apply_tags(path: Path, meta, cover, artist: str = "", title: str = ""):
    """Текстовые теги — через ffmpeg, обложка — через mutagen.
    Если album_artist не найден — всегда дублирует artist."""
    _ffmpeg_text_tags(path, meta, artist, title)

    if not cover:
        return
    try:
        audio_io.write_cover(path, cover)
    except Exception as ex:
        print(tr("  обложка не записалась: {ex}", ex=ex))


# ---------------------------------------------------------------------------
# Скачивание
# ---------------------------------------------------------------------------

# Если YouTube отдаёт 403, можно указать браузер, из которого взять cookies:
# "chrome", "firefox", "edge". None = не использовать.
COOKIES_BROWSER = None

def _format_attempts():
    """Родной AAC ~128 кбит/с берём как есть; иначе — лучшее аудио и перекодировка."""
    if audio_io.codec() == "m4a" and audio_io.bitrate() == 128:
        return ["bestaudio[ext=m4a]/bestaudio", "bestaudio/best"]
    return ["bestaudio/best", "bestaudio[ext=m4a]/bestaudio"]


def download(url, artist, title, base_path: Path):
    last_err = None
    codec = audio_io.codec()
    quality = str(audio_io.bitrate())
    for attempt, fmt in enumerate(_format_attempts()):
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "format": fmt,
            "retries": 5,
            "fragment_retries": 5,
            "outtmpl": str(base_path).replace("%", "%%") + ".%(ext)s",
            "writethumbnail": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": codec,
                "preferredquality": quality,
            }],
            "postprocessor_args": {
                "ffmpeg": [
                    "-metadata", f"artist={artist}",
                    "-metadata", f"title={title}",
                    "-metadata", f"album_artist={artist}",
                ]
            },
        }
        if COOKIES_BROWSER:
            opts["cookiesfrombrowser"] = (COOKIES_BROWSER,)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            audio_io.ensure_target(audio_io.find_downloaded(base_path))
            return
        except Exception as ex:
            last_err = ex
            time.sleep(3 * (attempt + 1))
    raise last_err


def main():
    text = LIST_FILE.read_text(encoding="utf-8-sig")
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    OUT_DIR.mkdir(exist_ok=True)

    if not (SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET):
        print(tr("Spotify: ключи не заданы, используется запасной режим без ключей (без жанров)."))
    codec = audio_io.codec()
    bitrate = audio_io.bitrate()
    native = codec == "m4a" and bitrate == 128
    note = " (родной AAC YouTube, без перекодировки)" if native \
        else " (перекодировка через ffmpeg)"
    print(tr("[скачивание] формат: {codec}, битрейт: {bitrate} кбит/с{note}",
             codec=codec.upper(), bitrate=bitrate, note=note))
    print(tr("[скачивание] итоговый пресет: {preset}", preset=audio_io.preset_id()))
    print(tr("Метаданные: MusicBrainz → Spotify → Deezer → Bandcamp → Last.fm → YouTube"))
    print(tr("Жанры приоритет: Last.fm → Deezer → остальные"))
    print(tr("Кэш:"), CACHE_FILE)

    cache = load_cache()
    searcher = yt_dlp.YoutubeDL(
        {"quiet": True, "no_warnings": True, "extract_flat": True, "noplaylist": False}
    )

    new_report = not Path("report.csv").exists()
    rep_f = open("report.csv", "a", newline="", encoding="utf-8-sig")
    rep = csv.writer(rep_f)
    if new_report:
        rep.writerow(["#", "запрос", "статус", "источник", "оценка", "найдено", "ссылка", "теги из"])
    nf_f = open("not_found.txt", "a", encoding="utf-8")

    stats = {"ok": 0, "review": 0, "missing": 0, "error": 0, "skipped": 0, "retagged": 0}

    for i, line in enumerate(lines, 1):
        artist, title = split_line(line)
        safe = safe_filename(line)
        base = OUT_DIR / safe
        out_file = audio_io.out_path(base)
        if out_file.exists():
            # уже скачан — дописать album artist и жанр, если их нет
            try:
                fields = audio_io.read_fields(out_file)
                cur_aart = fields.get("album_artist") or ""
                cur_genre = fields.get("genre") or ""
                if cur_aart and cur_genre:
                    stats["skipped"] += 1
                    continue
                # только album artist пустой, жанр уже есть — без сети
                if not cur_aart and cur_genre and artist:
                    apply_tags(out_file, {}, None, artist=artist, title=title)
                    stats["retagged"] += 1
                    print(f"[{i}/{len(lines)}] retag    {line} | albumartist={artist} | genre=(keep)")
                    continue
                meta, cover, used = collect_metadata(artist, title, "", cache)
                has_cover = fields.get("has_cover")
                apply_tags(out_file, meta, None if has_cover else cover, artist=artist, title=title)
                save_cache(cache)
                stats["retagged"] += 1
                g = ", ".join(meta.get("genres") or []) or "-"
                aa = (meta.get("album_artist") or artist or "-")
                print(f"[{i}/{len(lines)}] retag    {line} | albumartist={aa} | genre={g}")
            except Exception as ex:
                stats["skipped"] += 1
                print(f"[{i}/{len(lines)}] skip     {line} (retag failed: {ex})")
            continue

        accept, any_c = find_best(searcher, line, artist, title)
        if accept:
            total, label, found, url = accept
            meta_src = ""
            try:
                download(url, artist, title, base)
                # проверка, что файл не битый
                if not check_audio_ok(out_file):
                    if out_file.exists():
                        out_file.unlink()
                    raise RuntimeError("файл битый или слишком короткий/длинный")
                status = "ok"
            except Exception as ex:
                status = "error"
                print(tr("[{n}/{total}] ОШИБКА скачивания: {line} ({ex})", n=i,
                         total=len(lines), line=line, ex=ex))
            if status == "ok":
                yt_cover = pop_thumbnail(base)
                try:
                    meta, cover, used = collect_metadata(artist, title, url, cache)
                    cover = cover or yt_cover
                    apply_tags(out_file, meta, cover, artist=artist, title=title)
                    meta_src = "+".join(used)
                    save_cache(cache)
                    g = ", ".join(meta.get("genres") or []) or "-"
                    aa = (meta.get("album_artist") or artist or "-")
                    print(f"    albumartist={aa} | genre={g} | from={meta_src or '-'}")
                except Exception as ex:
                    print(tr("[{n}/{total}] не удалось записать теги: {line} ({ex})", n=i,
                             total=len(lines), line=line, ex=ex))
            rep.writerow([i, line, status, label, round(total), found, url, meta_src])
        elif any_c and any_c[0] >= REVIEW_MIN:
            total, label, found, url = any_c
            status = "review"
            rep.writerow([i, line, status, label, round(total), found, url, ""])
            nf_f.write(line + "\n")
        else:
            status = "missing"
            rep.writerow([i, line, status, "", "", "", "", ""])
            nf_f.write(line + "\n")

        stats[status] += 1
        rep_f.flush()
        nf_f.flush()
        print(f"[{i}/{len(lines)}] {status:8} {line}")
        time.sleep(SLEEP)

    rep_f.close()
    nf_f.close()
    save_cache(cache)
    print(tr("\nИтог:"), stats)
    print(tr("Сомнительные и ненайденные - в report.csv и not_found.txt"))


if __name__ == "__main__":
    main()
