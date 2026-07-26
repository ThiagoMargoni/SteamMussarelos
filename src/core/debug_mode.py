from __future__ import annotations

_local_assets = False

def set_local_assets(enabled: bool) -> None:
    global _local_assets
    _local_assets = bool(enabled)

def use_local_assets() -> bool:
    return _local_assets
