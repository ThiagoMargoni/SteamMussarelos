from __future__ import annotations

import subprocess
import threading
from pathlib import Path

import psutil

from src.models.game import Game

class ProcessManager:
    def __init__(self) -> None:
        self._running: dict[str, subprocess.Popen] = {}
        self._lock = threading.Lock()

    def is_running(self, game: Game) -> bool:
        with self._lock:
            proc = self._running.get(game.name)
            if proc and proc.poll() is None:
                game.pid = proc.pid
                return True
            if proc:
                self._running.pop(game.name, None)

        if game.install_path and game.executable:
            exe_path = Path(game.install_path) / game.executable
            if exe_path.exists():
                for p in psutil.process_iter(["pid", "exe"]):
                    try:
                        if p.info["exe"] and Path(p.info["exe"]).resolve() == exe_path.resolve():
                            game.pid = p.info["pid"]
                            return True
                    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                        continue
        return False

    def start(self, game: Game) -> tuple[bool, str]:
        if self.is_running(game):
            return False, "Jogo já está em execução."

        if not game.install_path or not game.executable:
            return False, "Executável não configurado."

        exe_path = Path(game.install_path) / game.executable
        if not exe_path.exists():
            return False, f"Executável não encontrado: {exe_path}"

        try:
            proc = subprocess.Popen(
                [str(exe_path)],
                cwd=str(game.install_path),
            )
            with self._lock:
                self._running[game.name] = proc
            game.pid = proc.pid
            return True, "Jogo iniciado."
        except OSError as exc:
            return False, str(exc)

    def stop(self, game: Game) -> tuple[bool, str]:
        stopped = False

        with self._lock:
            proc = self._running.pop(game.name, None)
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                stopped = True

        if game.pid:
            try:
                p = psutil.Process(game.pid)
                p.terminate()
                try:
                    p.wait(timeout=5)
                except psutil.TimeoutExpired:
                    p.kill()
                stopped = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if game.install_path and game.executable:
            exe_path = Path(game.install_path) / game.executable
            for p in psutil.process_iter(["pid", "exe"]):
                try:
                    if p.info["exe"] and Path(p.info["exe"]).resolve() == exe_path.resolve():
                        p.terminate()
                        stopped = True
                except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                    continue

        game.pid = None
        if stopped:
            return True, "Jogo encerrado."
        return False, "Nenhum processo encontrado."

    def refresh_all(self, games: list[Game]) -> None:
        for game in games:
            running = self.is_running(game)
            game.update_status(is_running=running)
