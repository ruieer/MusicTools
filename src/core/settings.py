"""Настройки в config.json рядом с приложением."""
import json
from pathlib import Path

from core.env import APP_DIR

CONFIG_FILE = APP_DIR / "config.json"

DEFAULTS = {
    "music_dir": "",             # пусто = папка music рядом с приложением
    "spotify_client_id": "",
    "spotify_client_secret": "",
    "lastfm_api_key": "",
    "accent_color": "#3b82f6",
    "audio_preset": "m4a_128",   # m4a/mp3 + 128/192/256
}


def load() -> dict:
    data = dict(DEFAULTS)
    try:
        data.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return data


def save(data: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def music_dir(data: dict) -> Path:
    return Path(data["music_dir"]) if data.get("music_dir") else APP_DIR / "music"


def audio_preset(data: dict) -> str:
    raw = str(data.get("audio_preset") or DEFAULTS["audio_preset"]).strip().lower()
    codec, _, rest = raw.partition("_")
    if codec not in ("m4a", "mp3"):
        codec = "m4a"
    if rest not in ("128", "192", "256"):
        rest = "128"
    return f"{codec}_{rest}"
