#!/usr/bin/env python3
"""
Изменение громкости (преампа) m4a- и mp3-файлов: звук физически становится тише или громче.

Запуск (из папки со скриптами):
    python gain.py

1. Введите значение в дБ:  -3  (тише),  +4  (громче),  -1,5  и т.д.
   Ориентир: ±1 дБ едва заметно, ±3 дБ - хорошо слышно, +6 дБ - примерно вдвое громче по амплитуде.
2. Вставьте, что обрабатывать (по одной строке, пустая строка = начать):
   пути ("Копировать как путь"), имена "Исполнитель - Название", путь к папке,
   имя txt-файла со списком, либо слово  все  - вся папка music.

Как работает: звук один раз перекодируется в том же формате с тем же (или не ниже 128 кбит/с) битрейтом,
все теги и обложка переносятся без изменений. При УСИЛЕНИИ включается ограничитель пиков,
чтобы не было клиппинга (хруста). Оригиналы сохраняются в gain_backup.

Важно: каждая обработка - это новое перекодирование, поэтому не гоняйте один файл через
скрипт много раз подряд. Нужно другое значение - возьмите оригинал из gain_backup и
положите его на место, потом примените нужное значение один раз.
"""
import csv
import os
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import audio_io
import download_music as dm
import retag as rt

KEEP_BACKUP = True
BACKUP_DIR = Path("gain_backup")
LOG = Path("gain_log.csv")
LIMITER_ON_BOOST = True        # ограничитель пиков при усилении (gain > 0)
LIMIT = 0.98                   # потолок пиков (1.0 = 0 dBFS)
MIN_KBPS, MAX_KBPS, DEFAULT_KBPS = 128, 320, 256
SANITY_MAX_DB = 30
# Сколько файлов обрабатывать одновременно. Кодер AAC в ffmpeg почти однопоточный,
# поэтому параллельные файлы дают почти линейное ускорение. 1 = по одному.
WORKERS = 11
_lock = threading.Lock()


def ask(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def parse_db(text):
    t = text.strip().lower().replace(",", ".").replace("дб", "").replace("db", "").strip()
    try:
        return float(t)
    except ValueError:
        return None


def bitrate_kbps(path):
    kb = audio_io.bitrate_kbps(path) or DEFAULT_KBPS
    return max(MIN_KBPS, min(MAX_KBPS, kb))


def length(path):
    return audio_io.duration(path)


def ffmpeg_gain(src, dst, gain_db, kbps):
    flt = f"volume={gain_db}dB"
    if gain_db > 0 and LIMITER_ON_BOOST:
        flt += f",alimiter=limit={LIMIT}:level=0"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
           "-map", "0:a:0", "-vn", "-af", flt,
           *audio_io.ffmpeg_codec_args(src, kbps), str(dst)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0 or not Path(dst).exists():
        raise RuntimeError((r.stderr or b"").decode("utf-8", "replace").strip()[-300:] or "ffmpeg")


def process(path, gain_db):
    tmp = path.with_name(path.stem + ".__gain" + path.suffix)
    try:
        old_len = length(path)
        ffmpeg_gain(path, tmp, gain_db, bitrate_kbps(path))
        new_len = length(tmp)
        if old_len and abs(new_len - old_len) > 1.5:
            raise RuntimeError(f"длина изменилась ({old_len:.1f}с -> {new_len:.1f}с), файл не тронут")
        audio_io.copy_tags(path, tmp)              # если упадёт - оригинал цел
        if KEEP_BACKUP:
            BACKUP_DIR.mkdir(exist_ok=True)
            bk = BACKUP_DIR / path.name
            if not bk.exists():                    # храним самый первый оригинал
                shutil.copy2(str(path), str(bk))
        shutil.move(str(tmp), str(path))
        return True
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def log_row(path, gain_db, status):
    with _lock:
        new = not LOG.exists()
        with open(LOG, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["время", "файл", "дБ", "статус"])
            w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), str(path), gain_db, status])


def main():
    dm.OUT_DIR.mkdir(exist_ok=True)
    gain = parse_db(ask("Изменение громкости в дБ (например -3 или +4): "))
    if gain is None:
        print("Не понял число. Пример: -3  или  +4,5")
        return
    if gain == 0:
        print("0 дБ - менять нечего.")
        return
    if abs(gain) > SANITY_MAX_DB:
        print(f"{gain:+g} дБ - слишком много (допустимо до ±{SANITY_MAX_DB}).")
        return

    print("\n(Можно написать  все  - обработать всю папку music.)")
    entries = rt.gather()
    if not entries:
        print("Ничего не введено.")
        return

    if any(e.strip().lower() in {"все", "всё", "all"} for e in entries):
        files = audio_io.list_audio(dm.OUT_DIR)
    else:
        index, files, missing = rt.music_index(), [], []
        for e in entries:
            found = rt.resolve(e, index)
            if not found:
                missing.append(e)
            files += [f for f in found if f not in files]
        if missing:
            print(f"\nНе нашёл файлы для {len(missing)} строк:")
            for m in missing:
                print("   -", m)
    if not files:
        return

    word = "ТИШЕ" if gain < 0 else "ГРОМЧЕ"
    ans = ask(f"\nСделать {len(files)} файл(ов) {word} на {abs(gain):g} дБ? [д/Enter=нет]: ").lower()
    if ans not in {"д", "да", "y", "yes"}:
        print("Отменено.")
        return

    workers = max(1, min(WORKERS, len(files)))
    print(f"\nПотоков: {workers} (меняется параметром WORKERS в начале gain.py)\n")
    ok = fail = done = 0
    t0 = time.time()

    def job(f):
        try:
            process(f, gain)
            return f, None
        except Exception as ex:
            return f, ex

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(job, f) for f in files]
        for fut in as_completed(futures):
            f, err = fut.result()
            done += 1
            if err is None:
                print(f"[{done}/{len(files)}] ✓ {f.name}  ({gain:+g} дБ)")
                log_row(f, gain, "ok")
                ok += 1
            else:
                print(f"[{done}/{len(files)}] ОШИБКА {f.name}: {err}")
                log_row(f, gain, f"error: {err}")
                fail += 1
    mins = (time.time() - t0) / 60
    print(f"\nЗатрачено: {mins:.1f} мин")
    print(f"\nГотово: успешно {ok}, с ошибками {fail}. Оригиналы: {BACKUP_DIR}, журнал: {LOG}")


if __name__ == "__main__":
    main()
