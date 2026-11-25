"""Язык интерфейса и сообщений движка: русский или английский.

Перевод ищется по русскому оригиналу как ключу, поэтому в русском режиме
tr() возвращает строку как есть, а словарь EN - единственное место переводов.
Подстановки в фигурных скобках заполняются уже после перевода, так что
порядок слов в английском может быть любым.
"""
from __future__ import annotations

RU = "ru"
EN_CODE = "en"
LANG = RU

# --- словари ---------------------------------------------------------------

EN: dict[str, str] = {
    # --- окно приложения ---------------------------------------------------
    "музыка для iPod": "music for iPod",
    "Остановить": "Stop",
    "Готово к работе": "Ready",
    "Очистить лог": "Clear log",
    "Вопросов нет": "No pending questions",
    "Ответ и Enter": "Answer and press Enter",
    "Отправить": "Send",
    "Уже выполняется другая задача": "Another task is already running",
    "Не могу открыть папку музыки: {ex}": "Cannot open the music folder: {ex}",
    "Работает: {title}": "Running: {title}",
    "Останавливаю…": "Stopping…",
    "{title}: {done} из {total}": "{title}: {done} of {total}",
    "Готово": "Done",
    "Остановлено": "Stopped",
    "Ошибка - см. лог": "Failed - see the log",
    "Введите ответ": "Enter an answer",
    "Задача работает…": "Task is running…",

    # --- навигация ---------------------------------------------------------
    "Загрузка списка": "Download a list",
    "По ссылке": "From a link",
    "Ручной разбор": "Manual review",
    "Теги": "Tags",
    "Обложки": "Covers",
    "Громкость": "Volume",
    "Передача на iPod": "Send to iPod",
    "Медиатека iPod": "iPod library",
    "Настройки": "Settings",

    # --- загрузка списка ---------------------------------------------------
    "Строки в формате «Исполнитель - Название», по одной на строку. Аудио ищется на YouTube "
    "и SoundCloud, теги и обложки - в MusicBrainz, Spotify, Deezer, Bandcamp и Last.fm. "
    "Формат и качество задаются в Настройках. Уже скачанные треки пропускаются.":
        "One «Artist - Title» line per track. Audio is searched on YouTube and SoundCloud, "
        "tags and artwork in MusicBrainz, Spotify, Deezer, Bandcamp and Last.fm. Format and "
        "quality live in Settings. Tracks you already have are skipped.",
    "Открыть .txt…": "Open .txt…",
    "Треков: {n}": "Tracks: {n}",
    "Запустить загрузку": "Start download",
    "Список треков": "Track list",
    "Текст": "Text",
    "Все файлы": "All files",
    "Список пуст - добавьте треки": "The list is empty - add some tracks",

    # --- по ссылке ---------------------------------------------------------
    "Скачать или заменить по ссылке": "Download or replace from a link",
    "Ссылки вводятся в строку ответа внизу. Режим «скачать» добавляет новый трек, "
    "режим «замена» подменяет уже скачанный - старый файл сохраняется в replaced_backup.":
        "Paste links into the answer line at the bottom. «download» adds a new track, "
        "«replace» swaps out one you already have - the old file is kept in replaced_backup.",
    "1. Нажмите «Начать».\n"
    "2. Вставьте ссылку на YouTube или SoundCloud и нажмите Enter.\n"
    "3. Чтобы закончить, нажмите «Выход».":
        "1. Press «Start».\n"
        "2. Paste a YouTube or SoundCloud link and press Enter.\n"
        "3. Press «Exit» when you are done.",
    "Начать": "Start",
    "Скачать по ссылке": "Download from a link",
    "Режим: замена": "Mode: replace",
    "Режим: скачать": "Mode: download",
    "Выход": "Exit",
    "По умолчанию": "Default",
    "Отмена": "Cancel",

    # --- ручной разбор -----------------------------------------------------
    "Ручной разбор ненайденных": "Review tracks that were not found",
    "Треки со статусом review, error или missing из report.csv. Для каждого можно выбрать вариант "
    "из поиска, вставить свою ссылку, пропустить или отложить. Ответы - кнопками под строкой ввода.":
        "Tracks with status review, error or missing from report.csv. For each one you can pick a "
        "search result, paste your own link, skip it or postpone it. Answers are the buttons under "
        "the answer line.",
    "Начать разбор": "Start review",
    "Отчёт report.csv найден.": "report.csv found.",
    "report.csv не найден: сначала запустите «Загрузка списка».":
        "report.csv not found: run «Download a list» first.",
    "Да, оставить": "Yes, keep it",
    "Нет": "No",
    "Скачать": "Download",
    "Дальше": "Next",
    "Пропустить": "Skip",
    "Поиск в браузере": "Search in browser",
    "Пропустить навсегда": "Skip forever",
    "На потом": "Later",

    # --- теги --------------------------------------------------------------
    "Теги для готовых файлов": "Tags for files you already have",
    "Вставьте пути к m4a/mp3, имена «Исполнитель - Название» или путь к .txt-файлу - по одному в строке. "
    "Альбом, год и жанр берутся из источников, ссылки на видео - из журналов скачивания.":
        "Paste m4a/mp3 paths, «Artist - Title» names or a .txt path - one per line. Album, year and "
        "genre come from the metadata sources, video links from the download logs.",
    "Заменять обложки на найденные": "Replace artwork with what was found",
    "Вводить вручную, если не нашлось": "Ask me when nothing was found",
    "Запустить": "Run",
    "Ничего не введено": "Nothing was entered",

    # --- обложки -----------------------------------------------------------
    "Исправить обложки": "Fix artwork",
    "Срезает однотонные полосы по краям обложек уже скачанных треков и приводит их к 500×500. "
    "Интернет не нужен, аудио не меняется.":
        "Trims flat borders around the artwork of tracks you already have and scales it to 500×500. "
        "No internet needed, audio is untouched.",
    "Папка: {path}": "Folder: {path}",

    # --- громкость ---------------------------------------------------------
    "Делает треки тише или громче: -3 - тише, +4 - громче (до ±30 дБ). Каждый файл перекодируется "
    "один раз, оригиналы сохраняются в gain_backup. Не применяйте разные значения к одному файлу подряд.":
        "Makes tracks quieter or louder: -3 is quieter, +4 is louder (up to ±30 dB). Every file is "
        "re-encoded once and the originals are kept in gain_backup. Do not apply different values to "
        "the same file repeatedly.",
    "Изменение, дБ:": "Change, dB:",
    "Что обработать - по одной строке: путь, «Исполнитель - Название» или «все»":
        "What to process - one per line: a path, «Artist - Title» or «all»",
    "Укажите, что обработать": "Nothing to process was given",
    "Да, применить": "Yes, apply",

    # --- настройки ---------------------------------------------------------
    "Папка с музыкой": "Music folder",
    "Выбрать…": "Browse…",
    "Открыть": "Open",
    "необязательно": "optional",
    "Ключи Spotify и Last.fm необязательны: без Spotify работает запасной режим "
    "(без жанров), без Last.fm жанры берутся из Deezer и MusicBrainz.":
        "Spotify and Last.fm keys are optional: without Spotify a fallback mode runs (no genres), "
        "without Last.fm genres come from Deezer and MusicBrainz.",
    "Формат и качество": "Format and quality",
    "YouTube обычно отдаёт AAC около 128 кбит/с. 192 и 256 — перекодировка "
    "через ffmpeg. MP3 всегда собирается ffmpeg из лучшего доступного аудио.":
        "YouTube usually serves AAC around 128 kbit/s. 192 and 256 are re-encoded through ffmpeg. "
        "MP3 is always assembled by ffmpeg from the best available audio.",
    "Формат": "Format",
    "кбит/с": "kbit/s",
    "Цвет оформления": "Accent color",
    "Свой…": "Custom…",
    "свой": "custom",
    "Сохранить": "Save",
    "Сохранить и перезапустить": "Save and restart",
    "Проверить обновления": "Check for updates",
    "Программа: {app}\nffmpeg: {ff}\nyt-dlp: {ydl}":
        "App: {app}\nffmpeg: {ff}\nyt-dlp: {ydl}",
    "найден": "found",
    "не найден": "not found",
    "НЕ найден (нужен для загрузки и громкости)": "NOT found (needed for downloads and volume)",
    "Настройки сохранены; цвет применён. Остальные параметры действуют со следующей задачи.":
        "Settings saved; the color is applied. Everything else takes effect with the next task.",
    "Настройки сохранены; новые параметры действуют со следующей задачи.":
        "Settings saved; the new values take effect with the next task.",
    "Проверка уже идёт": "A check is already running",
    "Проверяю обновления инструментов…": "Checking for tool updates…",
    "Проверка обновлений не удалась: {ex}": "The update check failed: {ex}",
    "Дождитесь окончания задачи, потом перезапустите":
        "Wait for the running task to finish, then restart",
    "Язык интерфейса": "Interface language",
    "Авто": "Auto",
    "Язык изменён - приложение перезапустится": "Language changed - the app will restart",

    # --- обновление инструментов без пересборки exe --------------------------
    "Обновить инструменты": "Update tools",
    "Обновление инструментов": "Tool update",
    "Обновление уже идёт": "An update is already running",
    "Дождитесь окончания задачи, потом обновите":
        "Wait for the running task to finish, then update",
    "Обновляю инструменты…": "Updating tools…",
    "Обновление не удалось: {ex}": "The update failed: {ex}",
    "yt-dlp: скачано {pct}%": "yt-dlp: {pct}% downloaded",
    "ffmpeg: скачано {pct}%": "ffmpeg: {pct}% downloaded",
    "{name}: скачано {pct}%": "{name}: {pct}% downloaded",
    "Скачиваю yt-dlp {old} → {new}…": "Downloading yt-dlp {old} → {new}…",
    "Скачиваю ffmpeg {old} → {new} (около 110 МБ)…":
        "Downloading ffmpeg {old} → {new} (about 110 MB)…",
    "yt-dlp обновлён до {v} (лежит в tools/lib)":
        "yt-dlp updated to {v} (stored in tools/lib)",
    "ffmpeg обновлён до {v} (лежит в tools/bin)":
        "ffmpeg updated to {v} (stored in tools/bin)",
    "yt-dlp {v} - уже последний": "yt-dlp {v} - already the latest",
    "ffmpeg {v} - уже последний": "ffmpeg {v} - already the latest",
    "yt-dlp обновить не удалось: {ex}": "Could not update yt-dlp: {ex}",
    "ffmpeg обновить не удалось: {ex}": "Could not update ffmpeg: {ex}",
    "ffmpeg: не удалось узнать последнюю версию":
        "ffmpeg: could not get the latest version",
    "Перезапустите программу, чтобы новый yt-dlp заработал.":
        "Restart the app so the new yt-dlp is used.",
    "на PyPI нет подходящего файла yt-dlp": "PyPI has no suitable yt-dlp file",
    "в скачанном файле нет пакета {name}": "the downloaded file has no {name} package",
    "в архиве нет файлов: {names}": "the archive has no files: {names}",
    "скачался пустой файл": "the download is empty",

    # --- передача на iPod --------------------------------------------------
    "Автономная запись аудио и iTunesDB без iTunes; проверено для iPod nano 2G. Перед записью "
    "создаётся резервная копия базы. Закройте iTunes; после передачи безопасно извлеките устройство.":
        "Writes audio and iTunesDB on its own, no iTunes involved; tested on the iPod nano 2G. The "
        "database is backed up before every write. Close iTunes and eject the device safely afterwards.",
    "iPod не найден": "No iPod found",
    "Поиск iPod…": "Looking for an iPod…",
    "Устройство": "Device",
    "Обновить": "Refresh",
    "Файлы или папка": "Files or folder",
    "Плейлист (необязательно)": "Playlist (optional)",
    "пусто - только в общую медиатеку": "empty - main library only",
    "Передать": "Transfer",
    "Добавлять обложки из тегов": "Add artwork from tags",
    "Извлечь iPod после передачи": "Eject the iPod after transfer",
    "Это точно nano 2G (если модель не определилась)": "It really is a nano 2G (if the model was not detected)",
    "Разрешить другие модели (экспериментально)": "Allow other models (experimental)",
    "Извлечь iPod": "Eject iPod",
    "Ошибка поиска: {exc}": "Search failed: {exc}",
    "{root}  {model}: {status}, свободно {mb} МБ": "{root}  {model}: {status}, {mb} MB free",
    "iPod не найден. Подключите устройство и убедитесь, что оно смонтировано "
    "как диск (режим «Использовать как диск»).":
        "No iPod found. Connect the device and make sure it is mounted as a disk "
        "(«Use as disk» mode).",
    "Выберите аудиофайлы (можно выделить несколько)": "Pick audio files (multiple selection works)",
    "Аудиофайлы": "Audio files",
    "Или выберите папку": "Or pick a folder",
    "Выбрано файлов: {n}": "Files selected: {n}",
    "Выберите файлы или папку": "Pick files or a folder",
    "Путь не существует": "That path does not exist",
    "Аудиофайлы не найдены": "No audio files found",
    "Извлечение iPod": "Ejecting the iPod",

    # --- медиатека iPod ----------------------------------------------------
    "Список треков на iPod: правка тегов в базе iPod и удаление треков вместе с файлами. "
    "Перед каждой записью создаётся резервная копия базы; iTunes должен быть закрыт.":
        "Tracks on the iPod: edit tags in the iPod database and delete tracks together with their "
        "files. The database is backed up before every write; iTunes must be closed.",
    "Название": "Title",
    "Исполнитель": "Artist",
    "Альбом": "Album",
    "Жанр": "Genre",
    "Год": "Year",
    "№": "#",
    "Длит.": "Length",
    "Исп. альбома": "Album artist",
    "№ трека": "Track #",
    "Найти iPod": "Find iPod",
    "Загрузить треки": "Load tracks",
    "Безопасно извлечь": "Eject safely",
    "поиск: название, исполнитель, альбом": "search: title, artist, album",
    "Сохранить изменения": "Save changes",
    "Удалить выбранные": "Delete selected",
    "Выбрать все": "Select all",
    "Показано {n} из {total}": "Showing {n} of {total}",
    "Выбрано {n} из {total}": "Selected {n} of {total}",
    "Выберите треки в списке": "Select tracks in the list first",
    "Поля не изменены": "No field was changed",
    "iPod не найден - подключите его и нажмите «Найти iPod»":
        "No iPod found - connect it and press «Find iPod»",
    "Дождитесь окончания текущей задачи перед извлечением":
        "Let the current task finish before ejecting",
    "Безопасное извлечение": "Safe eject",
    "Безопасно извлечь iPod ({root})?\n\nУбедитесь, что передача и редактирование завершены.":
        "Eject the iPod safely ({root})?\n\nMake sure transfers and edits are finished.",
    "Безопасное извлечение iPod": "Ejecting the iPod safely",
    "Чтение медиатеки iPod": "Reading the iPod library",
    "Изменение тегов на iPod": "Writing tags to the iPod",
    "Удаление треков с iPod": "Deleting tracks from the iPod",
    "Удаление с iPod": "Delete from the iPod",
    "Удалить с iPod треков: {n}?\n\n{names}{more}\n\n"
    "Аудиофайлы будут удалены с устройства.":
        "Delete {n} tracks from the iPod?\n\n{names}{more}\n\n"
        "The audio files will be removed from the device.",

    # --- ядро: настройки и извлечение ----------------------------------------
    "[настройки] формат/качество: {label} кбит/с  (пресет: {preset})":
        "[settings] format/quality: {label} kbit/s  (preset: {preset})",
    "Извлечение {root}...": "Ejecting {root}...",
    "iPod извлечён - можно отключать.": "iPod ejected - safe to unplug.",
    "Извлечь не удалось: закройте окна и программы, которые используют диск iPod, и повторите.":
        "Eject failed: close windows and programs that use the iPod disk and try again.",

    # --- проверка инструментов ----------------------------------------------
    "Проверка инструментов перед запуском:": "Checking the tools before start:",
    "  [{status}] {label}  {ver}  -  {why}": "  [{status}] {label}  {ver}  -  {why}",
    "  [ -- ] {label}  {ver}  -  {why}": "  [ -- ] {label}  {ver}  -  {why}",
    "есть": "yes",
    "нет": "no",
    "интерфейс": "user interface",
    "скачивание с YouTube/SoundCloud": "downloading from YouTube/SoundCloud",
    "теги и обложки": "tags and artwork",
    "сопоставление треков": "track matching",
    "метаданные из сети": "metadata from the network",
    "обработка обложек": "artwork processing",
    "передача на iPod": "transfer to the iPod",
    "загрузка, перекодировка, громкость, теги": "downloads, re-encoding, volume, tags",
    "проверка длительности трека": "track duration check",
    "среда выполнения": "runtime",
    "НЕ найден - положите в bin или в PATH": "NOT found - put it in bin or in PATH",
    "найден, но не запускается ({ex})": "found but does not start ({ex})",
    "найден, но не запускается": "found but does not start",
    "НЕ установлен ({kind})": "NOT installed ({kind})",
    "версия неизвестна": "version unknown",
    "Внимание: недоступно - {names}. Часть функций работать не будет.":
        "Warning: unavailable - {names}. Some features will not work.",
    "Все инструменты найдены - можно работать.": "All tools found - ready to go.",

    # --- проверка обновлений ------------------------------------------------
    "Проверка обновлений инструментов:": "Checking tool updates:",
    "не удалось узнать последнюю версию": "could not get the latest version",
    "актуальная версия": "up to date",
    "  [ ? ] {label}  {ver}  -  {why}": "  [ ? ] {label}  {ver}  -  {why}",
    "  [ ok] {label}  {ver}  -  {why}": "  [ ok] {label}  {ver}  -  {why}",
    "  [ ! ] {label}  {old} → {new}  -  скачайте из {where}":
        "  [ ! ] {label}  {old} → {new}  -  download from {where}",
    "  [ -- ] {label}  {ver}  -  обновлять нечего":
        "  [ -- ] {label}  {ver}  -  nothing to update",
    "  [ -- ] {label}  НЕ установлен  -  pip install {dist}":
        "  [ -- ] {label}  NOT installed  -  pip install {dist}",
    "  [ ! ] {label}  {old} → {new}  -  есть новая версия":
        "  [ ! ] {label}  {old} → {new}  -  a newer version exists",
    "Не удалось проверить (нет сети или сервис недоступен): {names}.":
        "Could not check (no network or the service is down): {names}.",
    "Доступны обновления: {n}.": "Updates available: {n}.",
    "ffmpeg обновляется заменой bin/ffmpeg.exe и bin/ffprobe.exe.":
        "ffmpeg is updated by replacing bin/ffmpeg.exe and bin/ffprobe.exe.",
    "Программа собрана в exe - встроенные пакеты обновляются только новой сборкой:":
        "The app is built into an exe - bundled packages are updated only by a new build:",
    "  пересоберите MusicTools (pyinstaller MusicTools.spec) и замените exe.":
        "  rebuild MusicTools (pyinstaller MusicTools.spec) and replace the exe.",
    "  Если сломалось скачивание с YouTube, новая сборка со свежим yt-dlp обычно решает проблему.":
        "  If YouTube downloads broke, a new build with a fresh yt-dlp usually fixes it.",
    "Обновить: pip install -U {names}": "Update: pip install -U {names}",
    "Все проверенные инструменты актуальны.": "All checked tools are up to date.",

    # --- громкость ----------------------------------------------------------
    "Изменение громкости в дБ (например -3 или +4): ":
        "Volume change in dB (for example -3 or +4): ",
    "Не понял число. Пример: -3  или  +4,5": "That is not a number. Example: -3  or  +4.5",
    "0 дБ - менять нечего.": "0 dB - nothing to change.",
    "{gain} дБ - слишком много (допустимо до ±{limit}).":
        "{gain} dB is too much (allowed up to ±{limit}).",
    "\n(Можно написать  все  - обработать всю папку music.)":
        "\n(You can type  all  to process the whole music folder.)",
    "Ничего не введено.": "Nothing was entered.",
    "\nНе нашёл файлы для {n} строк:": "\nNo files found for {n} lines:",
    "ТИШЕ": "QUIETER",
    "ГРОМЧЕ": "LOUDER",
    "\nСделать {n} файл(ов) {word} на {db} дБ? [д/Enter=нет]: ":
        "\nMake {n} file(s) {word} by {db} dB? [y/Enter=no]: ",
    "Отменено.": "Cancelled.",
    "\nПотоков: {n} (меняется параметром WORKERS в начале gain.py)\n":
        "\nWorkers: {n} (change WORKERS at the top of gain.py)\n",
    "[{done}/{total}] ✓ {name}  ({gain} дБ)": "[{done}/{total}] ✓ {name}  ({gain} dB)",
    "[{done}/{total}] ОШИБКА {name}: {err}": "[{done}/{total}] FAILED {name}: {err}",
    "[{n}/{total}] ОШИБКА {name}: {ex}": "[{n}/{total}] FAILED {name}: {ex}",
    "\nЗатрачено: {mins} мин": "\nTook: {mins} min",
    "\nГотово: успешно {ok}, с ошибками {fail}. Оригиналы: {backup}, журнал: {log}":
        "\nDone: {ok} ok, {fail} failed. Originals: {backup}, log: {log}",

    # --- обложки -----------------------------------------------------------
    "[{n}/{total}] исправлено: {name}": "[{n}/{total}] fixed: {name}",
    "[{n}/{total}] ошибка: {name} ({ex})": "[{n}/{total}] error: {name} ({ex})",
    "\nИсправлено: {fixed}, без полос: {unchanged}, без обложки: {none}, ошибок: {errors}":
        "\nFixed: {fixed}, no bars: {unchanged}, no artwork: {none}, errors: {errors}",

    # --- медиатека iPod ----------------------------------------------------
    "{root}: iPod не найден (нет iPod_Control/iTunes/iTunesDB)":
        "{root}: no iPod here (no iPod_Control/iTunes/iTunesDB)",
    "Закройте {names}: он может перезаписать базу iPod":
        "Close {names}: it may overwrite the iPod database",
    "На iPod осталась незавершённая запись базы; изменения отменены":
        "The iPod has an unfinished database write; changes cancelled",
    "iTunesDB повреждена или прочитана не полностью: {why}":
        "iTunesDB is damaged or was not fully read: {why}",
    "Треков на iPod: {n}": "Tracks on the iPod: {n}",
    "Резервная копия базы: {path}": "Database backup: {path}",
    "Сохранение iTunesDB...": "Saving iTunesDB...",
    "Записанная база не читается; восстановлена копия {path}":
        "The written database cannot be read; the backup {path} was restored",
    "Поле «{key}» должно быть числом: {value!r}": "Field «{key}» must be a number: {value!r}",
    "Нечего менять.": "Nothing to change.",
    "Название не может быть пустым": "The title cannot be empty",
    "Часть треков уже нет в базе - обновите список":
        "Some tracks are no longer in the database - reload the list",
    "Изменение треков: {n}; поля: {fields}": "Editing tracks: {n}; fields: {fields}",
    "Изменения не подтвердились для {n} треков": "Changes were not confirmed for {n} tracks",
    "Готово: изменения записаны.": "Done: changes written.",
    "Ничего не выбрано.": "Nothing was selected.",
    "Удаление: {artist} - {title}": "Deleting: {artist} - {title}",
    "Не удалось удалить {n} треков из базы": "Could not delete {n} tracks from the database",
    "Готово: удалено треков {done}, осталось {left}":
        "Done: {done} tracks deleted, {left} left",

    # --- теги --------------------------------------------------------------
    "   ! не m4a/mp3, пропускаю: {name}": "   ! not m4a/mp3, skipping: {name}",
    "Вставьте пути / имена треков / имя txt-файла (по одному в строке).":
        "Paste paths / track names / a txt file name (one per line).",
    "Пустая строка = начать обработку.\n": "An empty line starts processing.\n",
    "   из {name} загружено строк: {n}": "   loaded {n} lines from {name}",
    "   Не нашлось для {name}: {fields}": "   Nothing found for {name}: {fields}",
    "жанр": "genre",
    "альбом": "album",
    "год": "year",
    "   жанр: ": "   genre: ",
    "   альбом: ": "   album: ",
    "   год: ": "   year: ",
    "\nЗаменять обложки на найденные? [д = да / Enter = нет, добавлю только там, где обложки нет]: ":
        "\nReplace artwork with what was found? [y = yes / Enter = no, only fill in missing artwork]: ",
    "Если жанр/альбом/год не нашлись - вводить вручную по каждому файлу? [д = да / Enter = нет]: ":
        "If genre/album/year were not found - enter them manually for each file? [y = yes / Enter = no]: ",
    "\nК обработке: {n} файлов\n": "\nTo process: {n} files\n",
    "     записано: альбом={alb} | год={day} | жанр={gen} | источники: {src}":
        "     written: album={alb} | year={day} | genre={gen} | sources: {src}",
    "+обложка": "+artwork",
    "(ссылки на видео нет)": "(no video link)",
    "     ! ни один источник ничего не нашёл для этого трека":
        "     ! no source found anything for this track",
    "\nГотово: успешно {ok}, с ошибками {fail}. Журнал: {log}":
        "\nDone: {ok} ok, {fail} failed. Log: {log}",

    # --- ручной разбор ------------------------------------------------------
    "   скачиваю...": "   downloading...",
    "   ! файл выглядит подозрительно (пустой или длина вне диапазона {low}-{high} с)":
        "   ! the file looks suspicious (empty or out of the {low}-{high} s range)",
    "   всё равно оставить? [д/Enter=нет]: ": "   keep it anyway? [y/Enter=no]: ",
    "всё равно": "anyway",
    "   (теги записать не удалось: {ex})": "   (could not write tags: {ex})",
    "   ✓ готово:": "   ✓ done:",
    "   ОШИБКА скачивания: {ex}": "   DOWNLOAD FAILED: {ex}",
    "   скачать? [д]а / Enter=след. / [п]роп. / [о]поиск / ссылка / [й]=выход: ":
        "   download? [y]es / Enter=next / [s]kip / [o]pen search / link / [q]=quit: ",
    "скачать?": "download?",
    "   не понял, повторите": "   did not understand, try again",
    "\n   Варианты закончились.": "\n   No more options.",
    "   ссылка / [о]поиск в браузере / [п]роп. навсегда / Enter=на потом / [й]=выход: ":
        "   link / [o]pen search in browser / [s]kip forever / Enter=later / [q]=quit: ",
    "Не найден report.csv - запускайте из папки, где лежит основной скрипт.":
        "report.csv not found - run it from the folder with the main script.",
    "К разбору: {n} треков (review/error/missing).":
        "To review: {n} tracks (review/error/missing).",
    "\n{sep}\n[{k}/{total}] {line}   (статус: {status})":
        "\n{sep}\n[{k}/{total}] {line}   (status: {status})",
    "\nИтог:": "\nResult:",

    # --- ссылки ------------------------------------------------------------
    "   (не удалось прочитать данные по ссылке: {ex})":
        "   (could not read the data for this link: {ex})",
    "   Какой трек заменить?": "   Which track should be replaced?",
    "   Совпадений нет.": "   No matches.",
    "   номер / часть названия для поиска / Enter = отмена: ":
        "   number / part of the title to search / Enter = cancel: ",
    "   Видео: {title} | {channel} | {dur}": "   Video: {title} | {channel} | {dur}",
    "   отменено": "   cancelled",
    "   ✓ заменено: {name}   ({old} → {new})": "   ✓ replaced: {name}   ({old} → {new})",
    "   ОШИБКА, старый файл не тронут: {ex}": "   FAILED, the old file is untouched: {ex}",
    "   Имя файла [Enter = {hint}]: ": "   File name [Enter = {hint}]: ",
    "Имя файла": "File name",
    "ввести вручную": "type it manually",
    "   отменено (имя не задано)": "   cancelled (no name given)",
    "   ! файл уже есть: {name}\n   для подмены переключитесь в режим замены (введите з)":
        "   ! the file exists: {name}\n   switch to replace mode (type r) to swap it",
    "   ✓ скачано: {name}   ({dur})": "   ✓ downloaded: {name}   ({dur})",
    "Режим: СКАЧАТЬ. Вставляйте ссылки. Переключение: з = замена, с = скачать. Enter без текста = выход.":
        "Mode: DOWNLOAD. Paste links. Switch: r = replace, d = download. Empty Enter = exit.",
    "СКАЧАТЬ": "DOWNLOAD",
    "ЗАМЕНА": "REPLACE",
    "\n[{label}] Ссылка: ": "\n[{label}] Link: ",
    "Ссылка": "Link",
    "   режим: ЗАМЕНА существующего файла": "   mode: REPLACE an existing file",
    "   режим: СКАЧАТЬ новый трек": "   mode: DOWNLOAD a new track",
    "   нужна ссылка, начинающаяся с http (или з / с для смены режима)":
        "   a link starting with http is required (or r / d to change mode)",
    "   в папке {folder} нет m4a/mp3 - заменять нечего":
        "   no m4a/mp3 in {folder} - nothing to replace",

    # --- передача на iPod ---------------------------------------------------
    "Пропускаю неработающий ffmpeg: {exe}": "Skipping a broken ffmpeg: {exe}",
    "Для конвертации нужен ffmpeg из папки bin или переменной PATH":
        "Converting needs ffmpeg from the bin folder or PATH",
    "{exe} не запускается: рядом нет нужных DLL. Положите в bin полную (static/essentials) сборку ffmpeg.exe":
        "{exe} does not start: required DLLs are missing. Put a full (static/essentials) "
        "ffmpeg.exe build into bin",
    "Ошибка ffmpeg": "ffmpeg error",
    "На устройстве не найдена iTunesDB; передача отменена":
        "No iTunesDB on the device; transfer cancelled",
    "Не удалось удалить файл {why} {path}: {exc}":
        "Could not delete the file {path} ({why}): {exc}",
    "после отмены": "after cancel",
    "после отката": "after rollback",
    "{root}: нет iPod_Control/iTunes/iTunesDB - это не iPod или он не смонтирован":
        "{root}: no iPod_Control/iTunes/iTunesDB - this is not an iPod or it is not mounted",
    "iPod не найден: смонтированный том должен содержать iPod_Control/iTunes/iTunesDB":
        "No iPod found: the mounted volume must contain iPod_Control/iTunes/iTunesDB",
    "Подключено несколько iPod ({names}) - выберите нужный в списке":
        "Several iPods are connected ({names}) - pick the right one in the list",
    "Поиск подключённого iPod...": "Looking for a connected iPod...",
    "Устройство: {model} — {root}": "Device: {model} — {root}",
    "Закройте {names} перед автономной передачей: он может перезаписать базу iPod":
        "Close {names} before the standalone transfer: it may overwrite the iPod database",
    "Внимание: работает iTunesHelper - он может сам запустить iTunes. Если iTunes откроется, закройте его до конца передачи.":
        "Warning: iTunesHelper is running and may start iTunes. If iTunes opens, close it before "
        "the transfer finishes.",
    "Файлов для обработки: {n}": "Files to process: {n}",
    "Не найдено доступных аудиофайлов": "No usable audio files found",
    "Файл не найден: {path}": "File not found: {path}",
    "На iPod осталась незавершённая запись базы. Запустите передачу ещё раз после проверки iPod или восстановите копию из MusicToolsBackups":
        "The iPod has an unfinished database write. Run the transfer again after checking the iPod, "
        "or restore a backup from MusicToolsBackups",
    "iTunesDB повреждена или прочитана не полностью; запись отменена: {why}":
        "iTunesDB is damaged or was not fully read; write cancelled: {why}",
    "Эта модель не показывает обложки - они не добавляются.":
        "This model does not show artwork - it will not be added.",
    "Подготовка [{index}/{total}]: {name}": "Preparing [{index}/{total}]: {name}",
    "   пропуск, не удалось подготовить: {exc}": "   skipped, could not prepare it: {exc}",
    "Ни один файл не удалось подготовить": "None of the files could be prepared",
    "Сверка с треками в базе iPod...": "Checking against the tracks already on the iPod...",
    "Не удалось проверить существующий трек {path}: {exc}":
        "Could not check the existing track {path}: {exc}",
    "Проверено совпадающих треков: {done}/{total}":
        "Checked matching tracks: {done}/{total}",
    "Совпадающих по размеру треков: {n}": "Tracks with a matching size: {n}",
    "Уже на iPod: {name}": "Already on the iPod: {name}",
    "Повтор в выбранном списке: {name}": "Duplicate in the selected list: {name}",
    "Новых треков нет - база iPod не менялась.":
        "No new tracks - the iPod database was not changed.",
    "Недостаточно места на iPod: нужно около {need} МБ, свободно {free} МБ":
        "Not enough space on the iPod: about {need} MB needed, {free} MB free",
    "Добавление [{index}/{total}]: {name}": "Adding [{index}/{total}]: {name}",
    "   обложку добавить не удалось ({exc}), трек без обложки":
        "   could not add the artwork ({exc}), the track goes without it",
    "Плейлист «{name}»: треков {n}": "Playlist «{name}»: {n} tracks",
    "Не удалось определить, завершилась ли запись базы: {exc}":
        "Could not tell whether the database write finished: {exc}",
    "Скопированные файлы не удаляю; резервная копия: {path}":
        "Leaving the copied files in place; backup: {path}",
    "Проверка записанной базы...": "Verifying the written database...",
    "Не удалось подтвердить новые записи; база восстановлена из копии {path}":
        "Could not confirm the new entries; the database was restored from {path}",
    "Передача завершена: добавлено треков {added}, всего на iPod {total}":
        "Transfer finished: {added} tracks added, {total} on the iPod in total",
    "Извлечение iPod...": "Ejecting the iPod...",
    "Извлечь автоматически не удалось - используйте «Безопасное извлечение устройства».":
        "Automatic eject failed - use «Safely Remove Hardware». ",
    "Перед отключением используйте «Безопасное извлечение устройства» в Windows.":
        "Use «Safely Remove Hardware» in Windows before unplugging.",

    # --- скачивание ----------------------------------------------------------
    "  Pillow не справился, пробую ffmpeg:": "  Pillow failed, trying ffmpeg:",
    "  ffmpeg не найден в PATH - обложка не обработана":
        "  ffmpeg not found in PATH - artwork was not processed",
    "  ffmpeg не смог обработать обложку:": "  ffmpeg could not process the artwork:",
    "  не удалось сохранить кэш:": "  could not save the cache:",
    "  ffmpeg не найден — текстовые теги не записаны":
        "  ffmpeg not found - text tags were not written",
    "  ffmpeg не записал теги:": "  ffmpeg did not write the tags:",
    "  обложка не записалась: {ex}": "  artwork was not written: {ex}",
    "Spotify: ключи не заданы, используется запасной режим без ключей (без жанров).":
        "Spotify: no keys set, falling back to the keyless mode (no genres).",
    "[скачивание] формат: {codec}, битрейт: {bitrate} кбит/с{note}":
        "[download] format: {codec}, bitrate: {bitrate} kbit/s{note}",
    "[скачивание] итоговый пресет: {preset}": "[download] effective preset: {preset}",
    "Метаданные: MusicBrainz → Spotify → Deezer → Bandcamp → Last.fm → YouTube":
        "Metadata: MusicBrainz → Spotify → Deezer → Bandcamp → Last.fm → YouTube",
    "Жанры приоритет: Last.fm → Deezer → остальные":
        "Genre priority: Last.fm → Deezer → the rest",
    "Кэш:": "Cache:",
    "[{n}/{total}] ОШИБКА скачивания: {line} ({ex})":
        "[{n}/{total}] DOWNLOAD FAILED: {line} ({ex})",
    "[{n}/{total}] не удалось записать теги: {line} ({ex})":
        "[{n}/{total}] could not write tags: {line} ({ex})",
    "Сомнительные и ненайденные - в report.csv и not_found.txt":
        "Doubts and misses are in report.csv and not_found.txt",
}


# --- переключение языка ----------------------------------------------------

def system_lang() -> str:
    """Язык системы: русский Windows -> ru, иначе en."""
    try:
        import ctypes
        language_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return RU if (language_id & 0x3FF) == 0x19 else EN_CODE
    except Exception:  # noqa: BLE001 - не Windows или нет ctypes
        import locale
        try:
            name = locale.getlocale()[0] or ""
        except Exception:  # noqa: BLE001
            name = ""
        return RU if str(name).lower().startswith("ru") else EN_CODE


def set_lang(value) -> str:
    """auto/'' -> язык системы, en -> английский, остальное -> русский."""
    global LANG
    value = str(value or "").strip().lower()
    if value in ("", "auto"):
        LANG = system_lang()
    elif value.startswith("en"):
        LANG = EN_CODE
    else:
        LANG = RU
    return LANG


def current() -> str:
    return LANG


def is_english() -> bool:
    return LANG == EN_CODE


def tr(text: str, **fields) -> str:
    """Перевод строки и подстановка {полей}. Неизвестная строка остаётся как есть."""
    out = EN.get(text, text) if LANG == EN_CODE else text
    if fields:
        try:
            out = out.format(**fields)
        except (KeyError, IndexError, ValueError):
            pass
    return out


def has(text: str, ru: str) -> bool:
    """Есть ли в тексте движка русская фраза или её английский перевод.

    Нужно кнопкам-ответам: они ищут в вопросе узнаваемые слова, а вопрос
    приходит уже переведённым.
    """
    low = str(text).lower()
    if ru.lower() in low:
        return True
    english = EN.get(ru)
    return bool(english) and english.lower() in low
