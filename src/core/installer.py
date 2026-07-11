from __future__ import annotations

import os
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from src.core.archive import extract_archive
from src.core.downloader import download_file
from src.core.settings import Settings
from src.models.game import DownloadState, Game
from src.utils import format_bytes, format_speed

ProgressCallback = Callable[[Game], None]

class Installer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._active: dict[str, threading.Thread] = {}
        self._cancel_flags: dict[str, threading.Event] = {}

    def is_busy(self, game_name: str) -> bool:
        t = self._active.get(game_name)
        return t is not None and t.is_alive()

    def install(
        self,
        game: Game,
        on_progress: Optional[ProgressCallback] = None,
        is_update: bool = False,
    ) -> None:
        if self.is_busy(game.name):
            return

        cancel = threading.Event()
        self._cancel_flags[game.name] = cancel

        def _run() -> None:
            try:
                self._do_install(game, cancel, on_progress, is_update)
            finally:
                self._active.pop(game.name, None)
                self._cancel_flags.pop(game.name, None)

        t = threading.Thread(target=_run, daemon=True)
        self._active[game.name] = t
        t.start()

    def _notify(self, game: Game, cb: Optional[ProgressCallback]) -> None:
        if cb:
            cb(game)

    def _do_install(
        self,
        game: Game,
        cancel: threading.Event,
        on_progress: Optional[ProgressCallback],
        is_update: bool,
    ) -> None:
        games_folder = self.settings.games_folder
        if not games_folder:
            game.download_state = DownloadState.ERROR
            game.download_error = "Pasta de jogos não configurada."
            self._notify(game, on_progress)
            return

        game_dir = Path(games_folder) / game.name
        game.download_state = DownloadState.DOWNLOADING
        game.download_progress = 0.0
        game.download_error = ""
        self._notify(game, on_progress)

        if is_update and game_dir.exists():
            shutil.rmtree(game_dir, ignore_errors=True)

        game_dir.mkdir(parents=True, exist_ok=True)

        tmp_dir = Path(tempfile.mkdtemp())
        archive_path = tmp_dir / f"{game.name}.bin"

        try:
            archive_path = self._download(game, archive_path, cancel, on_progress)
            if cancel.is_set():
                return

            game.download_state = DownloadState.EXTRACTING
            game.download_progress = 0.0
            game.download_speed = ""
            self._notify(game, on_progress)

            extract_archive(archive_path, game_dir)
            self._write_version(game_dir, game.version)

            if not game.executable:
                game.executable = self._find_executable(game_dir)

            game.installed_version = game.version
            game.install_path = str(game_dir)
            game.update_status()

            self.settings.set_installed_game(
                game.name,
                game.version,
                str(game_dir),
                game.executable,
            )

            game.download_state = DownloadState.FINISHED
            game.download_progress = 100.0
            self._notify(game, on_progress)

        except Exception as exc:
            game.download_state = DownloadState.ERROR
            game.download_error = str(exc)
            if game_dir.exists():
                shutil.rmtree(game_dir, ignore_errors=True)
            game.installed_version = None
            game.install_path = None
            game.update_status()
            self._notify(game, on_progress)

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _download(
        self,
        game: Game,
        dest: Path,
        cancel: threading.Event,
        on_progress: Optional[ProgressCallback],
    ) -> Path:
        start = time.time()
        last_notify = start

        def on_chunk(downloaded: int, total: int) -> None:
            nonlocal last_notify
            now = time.time()
            if now - last_notify < 0.15 and total > 0 and downloaded < total:
                return

            elapsed = now - start
            speed = downloaded / elapsed if elapsed > 0 else 0
            game.download_speed = format_speed(speed)

            if total:
                game.download_progress = (downloaded / total) * 100
                game.download_size = f"{format_bytes(downloaded)} / {format_bytes(total)}"
            else:
                game.download_progress = min(99.0, max(1.0, downloaded / 1024 / 1024))
                game.download_size = format_bytes(downloaded)
            self._notify(game, on_progress)
            last_notify = now

        final_path = download_file(
            game.download,
            dest,
            on_chunk=on_chunk,
            cancel_check=cancel.is_set,
        )

        game.download_progress = 100.0
        self._notify(game, on_progress)
        return final_path

    def _write_version(self, game_dir: Path, ver: str) -> None:
        (game_dir / "version.txt").write_text(ver, encoding="utf-8")

    def _find_executable(self, game_dir: Path) -> Optional[str]:
        exes = list(game_dir.glob("*.exe"))
        if exes:
            return exes[0].name

        for sub in game_dir.iterdir():
            if sub.is_dir():
                sub_exes = list(sub.glob("*.exe"))
                if sub_exes:
                    return str(sub_exes[0].relative_to(game_dir)).replace("\\", "/")

        return None

    def remove_installation(self, game: Game) -> None:
        if game.install_path and os.path.isdir(game.install_path):
            shutil.rmtree(game.install_path, ignore_errors=True)

        game.installed_version = None
        game.install_path = None
        game.update_status()
        self.settings.remove_installed_game(game.name)
