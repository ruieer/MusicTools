# Music Tools

A Windows GUI for getting music onto an iPod: download from YouTube/SoundCloud, fix tags and
artwork, resolve unmatched tracks by hand, check loudness, repair covers, and transfer everything
to a mounted iPod.

## Download

The ready-to-run `MusicTools.exe` is in the **Releases** section of this repository. It is
self-contained: Python, yt-dlp, ffmpeg and ffprobe are already inside, so there is nothing to
install. Download the single file, put it in its own folder and run it.

- Windows 10/11, 64-bit. Administrator rights are not required.
- `config.json`, `report.csv`, `meta_cache.json`, logs and a `music` folder are created next to
  the exe. That folder is everything you need to keep.
- On the first run the exe unpacks the bundled ffmpeg/ffprobe into a temporary folder, so startup
  takes a few seconds.
- An internet connection is only needed to download music and look up artwork.

The exe is over 100 MB, so it is not stored in the repository; it is published as a release asset.

## Building the exe

You need Python 3.10+ and ffmpeg with ffprobe in `bin\`.

    pip install -r requirements.txt pyinstaller
    python -m PyInstaller --noconfirm --clean MusicTools.spec

The result is `dist\MusicTools.exe`. The GitHub build (Actions → **Build exe** → Run workflow) does
the same thing: it downloads ffmpeg, builds the exe and attaches it to the workflow artifacts; for
a tag such as `v1.0.0` it creates a release with that file.

## Transferring to an iPod

The "iPod Transfer" page writes tracks and the `iTunesDB` on its own, without launching iTunes and
without the iTunes API. The tested model is the iPod nano 2G.

- The device is found by its `iPod_Control` folder (the drive letter does not matter); if several
  iPods are connected, you pick the right one from a list.
- If the model cannot be identified, you have to confirm that it is a nano 2G. Other models that
  pygpod supports (1G-5G, mini, nano 1G/3G/4G, video, classic) are available only behind the
  "experimental" checkbox. Shuffle and nano 5G+ (SQLite database) are not supported.
- FLAC, Ogg, Opus and WMA are converted to AAC 256k (cached in `ipod_convert_cache`); tags and
  artwork are taken from the source file.
- Duplicates (SHA-256) are not copied; tracks can be added to a playlist right away.
- Artwork from tags is written to `ArtworkDB` (this can be switched off).
- Before any change, a dated copy of `iTunesDB`, `ArtworkDB`, `.ithmb` files and settings is made in
  `iPod_Control\iTunes\MusicToolsBackups`. After writing, the database is read back; if the new
  entries are not there, it is restored from the copy and the copied files are removed.
- iTunes must be closed (`iTunesHelper` may start it on its own - the program warns you). After the
  transfer the iPod can be ejected with the "Eject iPod" button.

The database writing is done with pygpod (LGPL-2.1-or-later): https://github.com/Bionded/pygpod.

## iPod Library

The "iPod Library" tab lists the tracks on the device (search, sort by column). You can change
title, artist, album, album artist, genre, year and track number for one track or for several at
once (only the changed fields are written) and delete selected tracks together with their files.
Tags are changed only in the `iTunesDB`; the audio files themselves are not rewritten. A backup of
the database is made before every write; deleted audio files are not part of it.

## Running from source

    pip install -r requirements.txt
    python src/app.py

ffmpeg and ffprobe must be in `PATH` or in the `bin\` folder.

The download format (M4A or MP3) and bitrate (128 / 192 / 256 kbps) are chosen in Settings.
YouTube usually serves AAC at around 128 kbps; higher quality and MP3 are produced by transcoding.

`config.json`, `report.csv`, `meta_cache.json`, logs and a `music` folder are created next to the
program by default.

## Layout

- `requirements.txt` - dependencies.
- `bin/` - ffmpeg and ffprobe.
- `src/` - source code: `app.py` (window), `ui/pages.py` (tool pages), `core/` (paths, settings,
  background runner), `engine/` (download and tagging scripts).
- `docs/` - notes on the iPod nano 2G.
- `backup/` - older copies of files, for reference (created locally, not in the repository).
- `ipod_convert_cache/` - conversion cache for the iPod (created at runtime).

## Notes

- yt-dlp goes stale quickly because of YouTube changes: `pip install -U yt-dlp`.
- Spotify and Last.fm keys are stored in `config.json` in plain text. They are optional; the
  Last.fm key can also be supplied through the `LASTFM_API_KEY` environment variable.
