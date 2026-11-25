"""Управление медиатекой iPod без iTunes: список треков, правка тегов, удаление.

Теги меняются только в iTunesDB (так их показывает iPod), аудиофайлы не переписываются.
Перед каждой записью - резервная копия базы, как при передаче.
"""
from __future__ import annotations

from pathlib import Path

import ipod_transfer as it
from core.i18n import tr

EDITABLE = ("title", "artist", "album", "albumartist", "genre", "year", "track_number")
NUMERIC = {"year", "track_number"}


def _open(root, write=False, assume_nano2g=False, allow_other_models=False):
    import pygpod
    root = Path(root)
    if not it.is_ipod_root(root):
        raise RuntimeError(tr("{root}: iPod не найден (нет iPod_Control/iTunes/iTunesDB)", root=root))
    if write:
        running = it._running(it.SYNC_PROCESSES)
        if running:
            raise RuntimeError(tr("Закройте {names}: он может перезаписать базу iPod", names=running))
        detected = pygpod.Device.from_mountpoint(str(root))
        ok, note = it.check_model(detected, assume_nano2g, allow_other_models)
        if not ok:
            raise RuntimeError(note)
        if pygpod.db.transaction.interrupted_commit(str(root)):
            raise RuntimeError(tr("На iPod осталась незавершённая запись базы; изменения отменены"))
    db = pygpod.Database(str(root), config=pygpod.DatabaseConfig(otg_on_save="keep"),
                         apply_play_counts=False, recover=False)
    if getattr(db, "damage", None):
        raise RuntimeError(tr("iTunesDB повреждена или прочитана не полностью: {why}",
                              why="; ".join(db.damage)))
    return root, db


def list_tracks(root) -> list:
    _root, db = _open(root)
    rows = []
    for t in db.tracks:
        row = {key: getattr(t, key) for key in EDITABLE}
        row.update(dbid=t.dbid, duration=t.duration_ms // 1000, size=t.file_size, path=t.ipod_path)
        rows.append(row)
    print(tr("Треков на iPod: {n}", n=len(rows)))
    return rows


def _save(root, db):
    import pygpod
    backup_dir = it._backup_device_databases(root)
    print(tr("Резервная копия базы: {path}", path=backup_dir))
    print(tr("Сохранение iTunesDB..."))
    db.save()
    verified = pygpod.Database(str(root), apply_play_counts=False, recover=False)
    if getattr(verified, "damage", None):
        it._restore_backup_files(backup_dir, root)
        raise RuntimeError(tr("Записанная база не читается; восстановлена копия {path}",
                              path=backup_dir))
    return verified


def _clean(key, value):
    if key in NUMERIC:
        value = str(value).strip()
        if not value:
            return 0
        if not value.isdigit():
            raise RuntimeError(tr("Поле «{key}» должно быть числом: {value!r}", key=key, value=value))
        return int(value)
    return "".join(ch for ch in str(value) if ch >= " ").strip()


def edit_tracks(root, dbids, fields: dict, **flags) -> int:
    """Записать fields (только изменённые поля) во все треки dbids."""
    fields = {k: _clean(k, v) for k, v in fields.items() if k in EDITABLE}
    if not fields or not dbids:
        print(tr("Нечего менять."))
        return 0
    if "title" in fields and not fields["title"]:
        raise RuntimeError(tr("Название не может быть пустым"))
    root, db = _open(root, write=True, **flags)
    by_id = {t.dbid: t for t in db.tracks}
    missing = [d for d in dbids if d not in by_id]
    if missing:
        raise RuntimeError(tr("Часть треков уже нет в базе - обновите список"))
    for dbid in dbids:
        for key, value in fields.items():
            setattr(by_id[dbid], key, value)
    print(tr("Изменение треков: {n}; поля: {fields}", n=len(dbids), fields=", ".join(fields)))
    verified = _save(root, db)
    check = {t.dbid: t for t in verified.tracks}
    wrong = [d for d in dbids if any(getattr(check[d], k) != v for k, v in fields.items())]
    if wrong:
        raise RuntimeError(tr("Изменения не подтвердились для {n} треков", n=len(wrong)))
    print(tr("Готово: изменения записаны."))
    return len(dbids)


def delete_tracks(root, dbids, **flags) -> int:
    """Удалить треки из базы и их файлы с iPod."""
    if not dbids:
        print(tr("Ничего не выбрано."))
        return 0
    root, db = _open(root, write=True, **flags)
    wanted = set(dbids)
    tracks = [t for t in db.tracks if t.dbid in wanted]
    if len(tracks) != len(wanted):
        raise RuntimeError(tr("Часть треков уже нет в базе - обновите список"))
    for t in tracks:
        print(tr("Удаление: {artist} - {title}", artist=t.artist, title=t.title))
    db.remove_tracks(tracks, delete_files=True)
    verified = _save(root, db)
    left = wanted & {t.dbid for t in verified.tracks}
    if left:
        raise RuntimeError(tr("Не удалось удалить {n} треков из базы", n=len(left)))
    print(tr("Готово: удалено треков {done}, осталось {left}",
             done=len(tracks), left=len(verified.tracks)))
    return len(tracks)
