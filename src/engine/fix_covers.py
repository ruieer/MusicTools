#!/usr/bin/env python3
"""
Чинит обложки УЖЕ скачанных m4a/mp3: срезает однотонные полосы по краям
и растягивает (или обрезает - см. THUMB_MODE в download_music.py) до 500x500.
Сеть не нужна, аудио не трогается.

Запуск:  python fix_covers.py            (папка с музыкой из настроек, по умолчанию music)
         python fix_covers.py "D:\\Музыка\\music"
Положите файл рядом с download_music.py.
"""
import io
import sys
from pathlib import Path

from PIL import Image

import audio_io
import download_music as dm


def main():
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else dm.OUT_DIR)
    fixed = unchanged = no_cover = errors = 0
    files = audio_io.list_audio(folder)
    for n, f in enumerate(files, 1):
        try:
            raw = audio_io.cover_bytes(f)
            if not raw:
                no_cover += 1
                continue
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            trimmed = dm.trim_bars(img)
            if trimmed.size == img.size:        # полос нет - не трогаем
                unchanged += 1
                continue
            data = dm.finish_cover(trimmed)
            audio_io.write_cover(f, data)
            fixed += 1
            print(f"[{n}/{len(files)}] исправлено: {f.name}")
        except Exception as ex:
            errors += 1
            print(f"[{n}/{len(files)}] ошибка: {f.name} ({ex})")
    print(f"\nИсправлено: {fixed}, без полос: {unchanged}, без обложки: {no_cover}, ошибок: {errors}")


if __name__ == "__main__":
    main()
