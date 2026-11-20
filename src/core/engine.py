"""Связка настроек с движком."""
import os
from pathlib import Path

import audio_io
import download_music as dm
import fix_covers
import gain
import manual_fix
import replace_live
import retag
import ipod_library
import ipod_transfer
from core.settings import music_dir

LIST_FILE = Path("current_list.txt")   # относительно APP_DIR (см. core.env.setup)


def apply(cfg: dict) -> None:
    """Перенести настройки в модули движка. Вызывать перед каждым запуском."""
    out = music_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    dm.OUT_DIR = out
    dm.SPOTIFY_CLIENT_ID = cfg.get("spotify_client_id", "").strip()
    dm.SPOTIFY_CLIENT_SECRET = cfg.get("spotify_client_secret", "").strip()
    dm.LASTFM_API_KEY = (cfg.get("lastfm_api_key", "").strip()
                         or os.environ.get("LASTFM_API_KEY", "").strip())
    preset = cfg.get("audio_preset") or "m4a_128"
    audio_io.set_preset(preset)
    print(f"[настройки] формат/качество: {audio_io.label()} кбит/с  (пресет: {audio_io.preset_id()})")


def write_list(lines) -> Path:
    LIST_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    dm.LIST_FILE = LIST_FILE
    return LIST_FILE


def run_download():
    dm.main()


def run_link():
    replace_live.main()


def run_manual():
    manual_fix.main()


def run_retag():
    retag.main()


def run_covers():
    fix_covers.main()


def run_gain():
    gain.main()


def run_ipod(source_files, device_root=None, assume_nano2g=False, allow_other_models=False,
             with_artwork=True, playlist_name="", eject_after=False):
    ipod_transfer.transfer(source_files, device_root=device_root, assume_nano2g=assume_nano2g,
                           allow_other_models=allow_other_models, with_artwork=with_artwork,
                           playlist_name=playlist_name, eject_after=eject_after)


def collect_audio(source):
    return ipod_transfer.collect_audio(source)


def eject_ipod(root):
    print(f"Извлечение {root}...")
    if ipod_transfer.eject(root):
        print("iPod извлечён - можно отключать.")
    else:
        print(ipod_transfer.eject_error() or
              "Извлечь не удалось: закройте окна и программы, которые используют диск iPod, и повторите.")


def find_ipods():
    return ipod_transfer.find_ipods()


def ipod_tracks(root):
    return ipod_library.list_tracks(root)


def ipod_edit(root, dbids, fields, **flags):
    ipod_library.edit_tracks(root, dbids, fields, **flags)


def ipod_delete(root, dbids, **flags):
    ipod_library.delete_tracks(root, dbids, **flags)
