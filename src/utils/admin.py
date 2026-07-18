from __future__ import annotations

import ctypes
import sys

def is_admin() -> bool:
    if sys.platform != "win32":
        return True
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def ensure_admin() -> None:
    if sys.platform != "win32" or is_admin():
        return

    params = " ".join(f'"{a}"' for a in sys.argv[1:])
    if getattr(sys, "frozen", False):
        executable = sys.executable
        args = params
    else:
        executable = sys.executable
        script = sys.argv[0]
        args = f'"{script}" {params}'.strip()

    ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, args, None, 1)
    if int(ret) <= 32:
        return
    sys.exit(0)
