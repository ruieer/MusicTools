#!/usr/bin/env python3
"""
Ручной дозабор: проходит по трекам со статусом review / error / missing
из report.csv, открывает вариант в браузере, вы отвечаете в консоли.

Положите рядом с download_music.py и report.csv, запускайте из той же папки:
    python manual_fix.py

Ответы:
    д / да / y     скачать этот вариант
    Enter / н      показать следующий вариант
    п / s          пропустить трек навсегда (больше не спрашивать)
    о / o          открыть в браузере поиск YouTube по этому треку
    https://...    вставить свою ссылку - скачается она
    й / q          выйти (прогресс сохраняется, можно продолжить позже)
Enter после последнего варианта - оставить трек на потом.

Скачивание, проверка файла, теги и обложка - те же функции, что в
download_music.py. Журнал решений: manual_log.csv, пропущенные: manual_skipped.txt
"""
import csv
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus

import yt_dlp

import audio_io
import download_music as dm

REPORT = Path("report.csv")
LOG = Path("manual_log.csv")
SKIPPED = Path("manual_skipped.txt")
STATUSES = {"review", "error", "missing"}

YES = {"y", "yes", "д", "да"}
NO = {"", "n", "no", "н", "нет", "т"}
SKIP = {"s", "skip", "п", "с", "ы", "пропустить"}
QUIT = {"q", "quit", "й", "в", "выход"}
OPEN = {"o", "о", "щ", "поиск"}   # латинская o, русская о, и клавиша o в русской раскладке


def fmt_dur(sec):
    if not sec:
        return "?:??"
    sec = int(sec)
    return f"{sec // 60}:{sec % 60:02d}"


def load_todo():
    last = {}
    with open(REPORT, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            last[row["запрос"]] = row            # последняя строка по треку = актуальный статус
    skipped = set()
    if SKIPPED.exists():
        skipped = set(SKIPPED.read_text(encoding="utf-8").splitlines())
    todo = []
    for line, row in last.items():
        if row["статус"] not in STATUSES or line in skipped:
            continue
        out = audio_io.out_path(dm.OUT_DIR / dm.safe_filename(line))
        if out.exists():                         # уже скачан (например, вручную)
            continue
        todo.append((line, row["статус"], row.get("ссылка") or "", row.get("найдено") or ""))
    return todo


def candidates(searcher, query, first_url, first_title):
    """Сначала вариант из отчёта (если был), потом свежие результаты поиска."""
    seen = set()
    if first_url:
        seen.add(first_url)
        yield {"title": first_title or "(из отчёта)", "channel": "", "duration": None,
               "url": first_url, "src": "из отчёта"}
    for prefix, label, n in (("ytsearch", "YouTube", 6), ("scsearch", "SoundCloud", 4)):
        try:
            info = searcher.extract_info(f"{prefix}{n}:{query}", download=False)
        except Exception:
            continue
        for e in (info or {}).get("entries") or []:
            if not e:
                continue
            url = e.get("webpage_url") or e.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            yield {"title": e.get("title") or "?", "duration": e.get("duration"),
                   "channel": e.get("channel") or e.get("uploader") or "",
                   "url": url, "src": label}


def ask(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return "q"


def grab(url, line, artist, title, cache):
    """Скачивает и теггит так же, как основной скрипт. True/False."""
    base = dm.OUT_DIR / dm.safe_filename(line)
    out = audio_io.out_path(base)
    try:
        print("   скачиваю...")
        dm.download(url, artist, title, base)
        out = audio_io.out_path(base)
        if not dm.check_audio_ok(out):
            print("   ! файл выглядит подозрительно (пустой или длина вне диапазона "
                  f"{dm.MIN_DUR}-{dm.MAX_DUR} с)")
            if ask("   всё равно оставить? [д/Enter=нет]: ").lower() not in YES:
                if out.exists():
                    out.unlink()
                dm.pop_thumbnail(base)
                return False
        yt_cover = dm.pop_thumbnail(base)
        try:
            meta, cover, used = dm.collect_metadata(artist, title, url, cache)
            dm.apply_tags(out, meta, cover or yt_cover, artist=artist, title=title)
            dm.save_cache(cache)
        except Exception as ex:
            print(f"   (теги записать не удалось: {ex})")
        print("   ✓ готово:", out.name)
        return True
    except Exception as ex:
        print(f"   ОШИБКА скачивания: {ex}")
        if out.exists():
            out.unlink()
        return False


def log(line, action, url=""):
    new = not LOG.exists()
    with open(LOG, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["запрос", "действие", "ссылка"])
        w.writerow([line, action, url])
    if action == "skipped":
        with open(SKIPPED, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def handle_track(searcher, cache, line, status, url, found):
    artist, title = dm.split_line(line)
    query = f"{artist} {title}".strip()
    search_page = "https://www.youtube.com/results?search_query=" + quote_plus(query)

    def answer_loop(c_url):
        """Диалог по одному варианту. Возвращает 'downloaded' / 'next' / 'skipped' / 'quit'."""
        while True:
            ans = ask("   скачать? [д]а / Enter=след. / [п]роп. / [о]поиск / ссылка / [й]=выход: ")
            low = ans.lower()
            if low in YES:
                if c_url and grab(c_url, line, artist, title, cache):
                    log(line, "downloaded", c_url)
                    return "downloaded"
                return "next"
            if low in NO:
                return "next"
            if low in SKIP:
                log(line, "skipped")
                return "skipped"
            if low in QUIT:
                return "quit"
            if low in OPEN:
                webbrowser.open(search_page)
                continue
            if low.startswith("http"):
                if grab(ans, line, artist, title, cache):
                    log(line, "downloaded", ans)
                    return "downloaded"
                continue
            print("   не понял, повторите")

    for c in candidates(searcher, query, url, found):
        dur = fmt_dur(c["duration"])
        ch = f" | {c['channel']}" if c["channel"] else ""
        print(f"\n   [{c['src']}] {c['title']}{ch} | {dur}")
        print(f"   {c['url']}")
        webbrowser.open(c["url"])
        res = answer_loop(c["url"])
        if res != "next":
            return res

    print("\n   Варианты закончились.")
    while True:
        ans = ask("   ссылка / [о]поиск в браузере / [п]роп. навсегда / Enter=на потом / [й]=выход: ")
        low = ans.lower()
        if low == "":
            return "later"
        if low in SKIP:
            log(line, "skipped")
            return "skipped"
        if low in QUIT:
            return "quit"
        if low in OPEN:
            webbrowser.open(search_page)
            continue
        if low.startswith("http"):
            if grab(ans, line, artist, title, cache):
                log(line, "downloaded", ans)
                return "downloaded"
            continue
        print("   не понял, повторите")


def main():
    if not REPORT.exists():
        print("Не найден report.csv - запускайте из папки, где лежит основной скрипт.")
        return
    dm.OUT_DIR.mkdir(exist_ok=True)
    todo = load_todo()
    print(f"К разбору: {len(todo)} треков (review/error/missing).")
    cache = dm.load_cache()
    searcher = yt_dlp.YoutubeDL(
        {"quiet": True, "no_warnings": True, "extract_flat": True, "noplaylist": False})

    stats = {"downloaded": 0, "skipped": 0, "later": 0}
    for k, (line, status, url, found) in enumerate(todo, 1):
        print(f"\n{'=' * 70}\n[{k}/{len(todo)}] {line}   (статус: {status})")
        res = handle_track(searcher, cache, line, status, url, found)
        if res == "quit":
            break
        stats[res] = stats.get(res, 0) + 1

    print("\nИтог:", stats)


if __name__ == "__main__":
    main()
