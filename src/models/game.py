from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

class GameStatus(Enum):
    NOT_INSTALLED = "Não instalado"
    INSTALLED = "Instalado"
    UPDATE_AVAILABLE = "Atualização disponível"
    RUNNING = "Em execução"

class DownloadState(Enum):
    IDLE = "idle"
    DOWNLOADING = "Baixando"
    EXTRACTING = "Extraindo"
    FINISHED = "Finalizado"
    ERROR = "Erro"

@dataclass
class Game:
    name: str
    version: str
    download: str
    icon: Optional[str] = None
    executable: Optional[str] = None

    installed_version: Optional[str] = None
    install_path: Optional[str] = None
    status: GameStatus = GameStatus.NOT_INSTALLED
    pid: Optional[int] = None

    download_progress: float = 0.0
    download_state: DownloadState = DownloadState.IDLE
    download_speed: str = ""
    download_size: str = ""
    download_error: str = ""

    def update_status(self, is_running: bool = False) -> None:
        if is_running:
            self.status = GameStatus.RUNNING

        elif not self.installed_version:
            self.status = GameStatus.NOT_INSTALLED
            
        elif self.installed_version != self.version:
            self.status = GameStatus.UPDATE_AVAILABLE
            
        else:
            self.status = GameStatus.INSTALLED

@dataclass
class LauncherInfo:
    version: str = "1.0.0"
    download: Optional[str] = None
    latest_version: Optional[str] = None

@dataclass
class Catalog:
    launcher: LauncherInfo = field(default_factory=LauncherInfo)
    games: list[Game] = field(default_factory=list)
