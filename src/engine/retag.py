#!/usr/bin/env python3
"""
Прогон готовых m4a/mp3 через выставление тегов (те же источники, что в
download_music.py: MusicBrainz, Deezer, Last.fm + Spotify, если заданы ключи).

Запуск (из папки со скриптами):
    python retag.py

Что можно вставлять (по одной строке, пустая строка = начать):
  * пути, скопированные через "Копировать как путь" (с кавычками или без)
  * имя трека как в списке:  Исполнитель - Название  (ищется в папке music)
  * путь к папке - обработаются все .m4a и .mp3 внутри
  * имя txt-файла со списком таких строк (например  fix.txt)

Исполнитель и название берутся из имени файла ("Исполнитель - Название");
если в имени нет " - ", то из уже записанных в файл тегов.
Аудио не перекодируется, меняются только теги (и, по желанию, обложка).
"""
import csv
import re
import time
from pathlib import Path

from rapidfuzz import fuzz

import audio_io
import download_music as dm
from core.i18n import tr

FORCE_REFRESH = True      # True = игнорировать кэш и искать теги заново
FULL_SEARCH = True        # True = включить медленные, но полезные для андерграунда источники
                          # (Bandcamp и Spotify без ключей) - они дают альбом и год
FUZZY_MIN = 92            # автопринятие неточного имени из папки music (0-100)
LOG = Path("retag_log.csv")


def ask(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def clean(s):
    return s.strip().strip("\u202a\u200e\u200f").strip().strip("\"'").strip()


def file_info(path):
    """(artist, title, has_cover) из имени файла, при необходимости из тегов."""
    artist, title = dm.split_line(path.stem)
    fields = audio_io.read_fields(path)
    if not artist:
        artist = fields.get("artist") or ""
    if not artist or not title:
        title = title or fields.get("title") or ""
    return artist, title or path.stem, fields.get("has_cover")


def load_urls():
    """Ссылки, с которых файлы были скачаны (из отчётов/журналов), по имени трека.
    Нужны, чтобы подтянуть теги из самого видео (альбом/год/жанр), как при первой загрузке."""
    urls = {}

    def add(name, url):
        if name and url and url.startswith("http"):
            urls[dm.norm(name)] = url

    sources = [   # порядок важен: более поздние источники перекрывают ранние
        ("report.csv", "запрос", "ссылка", "статус", "ok", False),
        ("manual_log.csv", "запрос", "ссылка", "действие", "downloaded", False),
        ("download_log.csv", "файл", "ссылка", None, None, True),
        ("replace_log.csv", "файл", "ссылка", None, None, True),
    ]
    for fn, name_col, url_col, st_col, st_val, is_file in sources:
        path = Path(fn)
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    if st_col and row.get(st_col) != st_val:
                        continue
                    name = row.get(name_col) or ""
                    if is_file:
                        name = audio_io.strip_audio_suffix(name)
                    elif not is_file:
                        name = dm.safe_filename(name)
                    add(name, row.get(url_col) or "")
        except Exception:
            pass
    return urls


def read_back(path):
    """Что реально записано в файле: (альбом, год, жанр)."""
    fields = audio_io.read_fields(path)
    return fields.get("album") or "", fields.get("date") or "", fields.get("genre") or ""


def music_index():
    return {dm.norm(f.stem): f for f in audio_io.list_audio(dm.OUT_DIR)}


def resolve(entry, index):
    """Строка -> список путей к m4a/mp3 ([] если не нашли)."""
    e = clean(entry)
    if not e:
        return []
    try:
        p = Path(e)
        if p.is_dir():
            return audio_io.list_audio(p, recursive=True)
        if p.is_file():
            if audio_io.is_audio(p):
                return [p]
            print(tr("   ! не m4a/mp3, пропускаю: {name}", name=p.name))
            return []
    except OSError:
        pass
    name = audio_io.strip_audio_suffix(e)
    cand = audio_io.find_existing(dm.OUT_DIR / dm.safe_filename(name))
    if cand:
        return [cand]
    key = dm.norm(name)
    if key in index:
        return [index[key]]
    best = max(index, key=lambda k: fuzz.token_sort_ratio(key, k), default=None)
    if best and fuzz.token_sort_ratio(key, best) >= FUZZY_MIN:
        return [index[best]]
    return []


def gather():
    print(tr("Вставьте пути / имена треков / имя txt-файла (по одному в строке)."))
    print(tr("Пустая строка = начать обработку.\n"))
    entries = []
    while True:
        line = ask("> ")
        if not line:
            break
        c = clean(line)
        if c.lower().endswith(".txt") and Path(c).is_file():
            rows = Path(c).read_text(encoding="utf-8-sig").splitlines()
            rows = [r for r in rows if r.strip()]
            entries += rows
            print(tr("   из {name} загружено строк: {n}", name=Path(c).name, n=len(rows)))
        elif line.count('"') >= 2:                  # несколько путей в кавычках в одной строке
            entries += re.findall(r'"([^"]+)"', line)
        else:
            entries.append(line)
    return entries


def fill_manually(path, meta):
    """Спрашивает недостающие жанр/альбом/год. Enter = пропустить поле."""
    need = [k for k in ("genres", "album", "date") if not meta.get(k)]
    if not need:
        return
    print(tr("   Не нашлось для {name}: {fields}", name=path.name, fields=", ".join(
        {"genres": tr("жанр"), "album": tr("альбом"), "date": tr("год")}[k] for k in need)))
    if "genres" in need:
        v = ask(tr("   жанр: "))
        if v:
            meta["genres"] = [v]
    if "album" in need:
        v = ask(tr("   альбом: "))
        if v:
            meta["album"] = v
    if "date" in need:
        v = ask(tr("   год: "))
        if v:
            meta["date"] = v


def log_row(path, artist, title, status, used):
    new = not LOG.exists()
    with open(LOG, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["файл", "исполнитель", "название", "статус", "источники"])
        w.writerow([str(path), artist, title, status, used])


def main():
    dm.OUT_DIR.mkdir(exist_ok=True)
    if FULL_SEARCH:
        dm.USE_BANDCAMP = True
        dm.USE_SPOTIFY_KEYLESS = True
    entries = gather()
    if not entries:
        print(tr("Ничего не введено."))
        return

    index = music_index()
    files, missing = [], []
    for e in entries:
        found = resolve(e, index)
        if not found:
            missing.append(e)
        for f in found:
            if f not in files:
                files.append(f)
    if missing:
        print(tr("\nНе нашёл файлы для {n} строк:", n=len(missing)))
        for m in missing:
            print("   -", m)
    if not files:
        return

    ans = ask(tr("\nЗаменять обложки на найденные? [д = да / Enter = нет, "
                 "добавлю только там, где обложки нет]: ")).lower()
    replace_cover = ans in {"д", "да", "y", "yes"}

    ans = ask(tr("Если жанр/альбом/год не нашлись - вводить вручную по каждому файлу? "
                 "[д = да / Enter = нет]: ")).lower()
    manual = ans in {"д", "да", "y", "yes"}

    print(tr("\nК обработке: {n} файлов\n", n=len(files)))
    cache = dm.load_cache()
    urls = load_urls()
    ok = fail = 0
    for i, f in enumerate(files, 1):
        artist, title, has_cover = file_info(f)
        try:
            url = urls.get(dm.norm(f.stem), "")
            if FORCE_REFRESH:
                cache.pop(dm.cache_key(artist, title), None)
            meta, cover, used = dm.collect_metadata(artist, title, url, cache)
            if manual:
                fill_manually(f, meta)       # спросит то, что не нашлось (Enter = пропустить)
            use_cover = cover if (replace_cover or not has_cover) else None
            dm.apply_tags(f, meta, use_cover, artist=artist, title=title)
            dm.save_cache(cache)
            src = "+".join(used) or "-"
            alb, day, gen = read_back(f)
            print(f"[{i}/{len(files)}] {f.name}")
            print(tr("     записано: альбом={alb} | год={day} | жанр={gen} | источники: {src}",
                     alb=alb or "-", day=day or "-", gen=gen or "-", src=src)
                  + (" | " + tr("+обложка") if use_cover else "")
                  + ("" if url else " | " + tr("(ссылки на видео нет)")))
            if not (alb or day or gen):
                print(tr("     ! ни один источник ничего не нашёл для этого трека"))
            log_row(f, artist, title, "ok", src)
            ok += 1
        except Exception as ex:
            print(tr("[{n}/{total}] ОШИБКА {name}: {ex}", n=i, total=len(files),
                     name=f.name, ex=ex))
            log_row(f, artist, title, f"error: {ex}", "")
            fail += 1
        time.sleep(dm.SLEEP)

    print(tr("\nГотово: успешно {ok}, с ошибками {fail}. Журнал: {log}",
             ok=ok, fail=fail, log=LOG))


if __name__ == "__main__":
    main()
