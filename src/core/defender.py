from __future__ import annotations

import subprocess
import sys
from pathlib import Path

class DefenderService:
    """Gerencia exclusões do Microsoft Defender no Windows."""

    @staticmethod
    def is_windows() -> bool:
        return sys.platform == "win32"

    @staticmethod
    def is_excluded(folder: str) -> bool:
        if not DefenderService.is_windows():
            return True

        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-MpPreference).ExclusionPath -join '|'",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if result.returncode != 0:
                return False
            exclusions = result.stdout.strip().lower()
            return folder.lower() in exclusions
        except (subprocess.SubprocessError, OSError):
            return False

    @staticmethod
    def add_exclusion(folder: str) -> tuple[bool, str]:
        if not DefenderService.is_windows():
            return True, "Sistema não-Windows — exclusão ignorada."

        folder = str(Path(folder).resolve())
        if DefenderService.is_excluded(folder):
            return True, "Pasta já está nas exclusões do Defender."

        try:
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"Add-MpPreference -ExclusionPath '{folder}'",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            if result.returncode == 0:
                return True, "Exclusão adicionada ao Microsoft Defender."
            return False, result.stderr.strip() or "Falha ao adicionar exclusão (execute como administrador)."
        except (subprocess.SubprocessError, OSError) as exc:
            return False, str(exc)
