#!/usr/bin/env python3
"""
Скачивание и замена по ссылке (два режима в одном скрипте).

Положите рядом с download_music.py, запускайте из той же папки:
    python replace_live.py

РЕЖИМ "СКАЧАТЬ" (по умолчанию): вставили ссылку -> скачался новый трек.
  Имя предлагается из данных видео, Enter = принять, либо впишите свой
  вариант в формате "Исполнитель - Название". Теги/жанр/обложка подтягиваются
  тем же способом, что в download_music.py.

РЕЖИМ "ЗАМЕНА": вставили ссылку -> выбрали, какой файл из music заменить ->
  новое аудио скачивается, ВСЕ теги и обложка переносятся из старого файла,
  файл подменяется (имя прежнее). Старый сохраняется в replaced_backup
  (KEEP_BACKUP = False - не сохранять).

Переключение режимов - вводом вместо ссылки:
    з   (или r)  режим замены
    с   (или d)  режим скачивания
    Enter        выход
Журналы: download_log.csv (новые), replace_log.csv (замены)
"""
import csv
import re
import shutil
import time
from pathlib import Path

import yt_dlp
from rapidfuzz import fuzz

import audio_io
import download_music as dm
from core.i18n import tr

KEEP_BACKUP = True
BACKUP_DIR = Path("replaced_backup")
TMP_DIR = Path("_replace_tmp")
LOG = Path("replace_log.csv")
SHOW = 6                      # сколько похожих файлов показывать


def norm(s):
    s = (s or "").lower().replace("ё", "е")
    return re.sub(r"[^\w]+", " ", s).strip()


def fmt_dur(sec):
    sec = int(sec or 0)
    return f"{sec // 60}:{sec % 60:02d}"


def ask(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def video_info(url):
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True,
                               "noplaylist": True, "skip_download": True}) as ydl:
            return ydl.extract_info(url, download=False) or {}
    except Exception as ex:
        print(tr("   (не удалось прочитать данные по ссылке: {ex})", ex=ex))
        return {}


def best_matches(query, files, limit=SHOW):
    q = norm(query)
    scored = [(fuzz.token_set_ratio(q, norm(f.stem)), f) for f in files]
    scored.sort(key=lambda x: -x[0])
    return scored[:limit]


def pick_target(files, query):
    """Диалог выбора файла. Возвращает Path или None."""
    while True:
        matches = best_matches(query, files) if query else []
        if matches:
            print(tr("   Какой трек заменить?"))
            for i, (sc, f) in enumerate(matches, 1):
                print(f"   {i}) {f.stem}   ({int(sc)}%)")
        else:
            print(tr("   Совпадений нет."))
        ans = ask(tr("   номер / часть названия для поиска / Enter = отмена: "))
        if not ans:
            return None
        if ans.isdigit() and 1 <= int(ans) <= len(matches):
            return matches[int(ans) - 1][1]
        query = ans                    # любой другой ввод = новый поисковый запрос


def length(path):
    return audio_io.duration(path)


def replace_one(url, files):
    info = video_info(url)
    if info:
        print(tr("   Видео: {title} | {channel} | {dur}", title=info.get('title', '?'),
                 channel=info.get('channel') or info.get('uploader') or '',
                 dur=fmt_dur(info.get('duration'))))
    query = f"{info.get('title', '')} {info.get('channel') or info.get('uploader') or ''}".strip()
    target = pick_target(files, query)
    if target is None:
        print(tr("   отменено"))
        return False

    artist, title = dm.split_line(target.stem)
    shutil.rmtree(TMP_DIR, ignore_errors=True)
    TMP_DIR.mkdir()
    base = TMP_DIR / "new"
    try:
        print(tr("   скачиваю..."))
        dm.download(url, artist, title, base)
        dm.pop_thumbnail(base)               # превью не нужно - обложка останется старая
        new = audio_io.find_downloaded(base)
        if not new.exists() or length(new) < 1:
            raise RuntimeError("скачанный файл пустой или не создался")

        dest = target.with_suffix(new.suffix)
        old_len, new_len = length(target), length(new)
        audio_io.copy_tags(target, new)      # если упадёт - старый файл не тронут

        if KEEP_BACKUP:
            BACKUP_DIR.mkdir(exist_ok=True)
            bk = BACKUP_DIR / target.name
            if bk.exists():
                bk = BACKUP_DIR / f"{target.stem}.{int(time.time())}{target.suffix}"
            shutil.move(str(target), str(bk))
        else:
            target.unlink()
        if dest.exists() and dest != target:
            dest.unlink()
        shutil.move(str(new), str(dest))

        print(tr("   ✓ заменено: {name}   ({old} → {new})", name=dest.name,
                 old=fmt_dur(old_len), new=fmt_dur(new_len)))
        is_new = not LOG.exists()
        with open(LOG, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            if is_new:
                w.writerow(["файл", "ссылка", "было, с", "стало, с"])
            w.writerow([dest.name, url, int(old_len), int(new_len)])
        return True
    except Exception as ex:
        print(tr("   ОШИБКА, старый файл не тронут: {ex}", ex=ex))
        return False
    finally:
        shutil.rmtree(TMP_DIR, ignore_errors=True)


DOWNLOAD_LOG = Path("download_log.csv")


def guess_name(info):
    """Предлагает имя 'Исполнитель - Название' по данным видео."""
    if info.get("artist") and info.get("track"):
        return f"{info['artist']} - {info['track']}"
    title = (info.get("title") or "").strip()
    if " - " in title:
        return title
    chan = re.sub(r"\s*-\s*Topic$", "", info.get("channel") or info.get("uploader") or "")
    return f"{chan} - {title}" if chan and title else title


def download_new(url, cache):
    """Режим 'скачать': новый трек по ссылке, теги и обложка как в основном скрипте."""
    info = video_info(url)
    if info:
        print(tr("   Видео: {title} | {channel} | {dur}", title=info.get('title', '?'),
                 channel=info.get('channel') or info.get('uploader') or '',
                 dur=fmt_dur(info.get('duration'))))
    guess = guess_name(info)
    name = ask(tr("   Имя файла [Enter = {hint}]: ",
                  hint=guess or tr("ввести вручную"))) or guess
    if not name:
        print(tr("   отменено (имя не задано)"))
        return False

    artist, title = dm.split_line(name)
    dm.OUT_DIR.mkdir(exist_ok=True)
    base = dm.OUT_DIR / dm.safe_filename(name)
    out = audio_io.find_existing(base)
    if out:
        print(tr("   ! файл уже есть: {name}\n"
                 "   для подмены переключитесь в режим замены (введите з)", name=out.name))
        return False
    try:
        print(tr("   скачиваю..."))
        dm.download(url, artist, title, base)
        yt_cover = dm.pop_thumbnail(base)
        out = audio_io.out_path(base)
        if not out.exists() or length(out) < 1:
            raise RuntimeError("скачанный файл пустой или не создался")
        try:
            meta, cover, used = dm.collect_metadata(artist, title, url, cache)
            dm.apply_tags(out, meta, cover or yt_cover, artist=artist, title=title)
            dm.save_cache(cache)
        except Exception as ex:
            print(tr("   (теги записать не удалось: {ex})", ex=ex))
        print(tr("   ✓ скачано: {name}   ({dur})", name=out.name,
                 dur=fmt_dur(length(out))))
        is_new = not DOWNLOAD_LOG.exists()
        with open(DOWNLOAD_LOG, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            if is_new:
                w.writerow(["файл", "ссылка"])
            w.writerow([out.name, url])
        return True
    except Exception as ex:
        print(tr("   ОШИБКА скачивания: {ex}", ex=ex))
        if out and out.exists():
            out.unlink()
        dm.pop_thumbnail(base)
        return False


MODE_REPLACE = {"з", "r", "к", "замена"}
MODE_DOWNLOAD = {"с", "d", "в", "скачать"}


def main():
    dm.OUT_DIR.mkdir(exist_ok=True)
    cache = dm.load_cache()
    mode = "download"
    print(tr("Режим: СКАЧАТЬ. Вставляйте ссылки. "
             "Переключение: з = замена, с = скачать. Enter без текста = выход."))
    while True:
        label = tr("СКАЧАТЬ") if mode == "download" else tr("ЗАМЕНА")
        ans = ask(tr("\n[{label}] Ссылка: ", label=label))
        low = ans.lower()
        if not ans:
            break
        if low in MODE_REPLACE:
            mode = "replace"
            print(tr("   режим: ЗАМЕНА существующего файла"))
            continue
        if low in MODE_DOWNLOAD:
            mode = "download"
            print(tr("   режим: СКАЧАТЬ новый трек"))
            continue
        if not low.startswith("http"):
            print(tr("   нужна ссылка, начинающаяся с http (или з / с для смены режима)"))
            continue
        if mode == "download":
            download_new(ans, cache)
        else:
            files = audio_io.list_audio(dm.OUT_DIR)   # обновляем список после скачиваний
            if not files:
                print(tr("   в папке {folder} нет m4a/mp3 - заменять нечего", folder=dm.OUT_DIR))
                continue
            replace_one(ans, files)


if __name__ == "__main__":
    main()
