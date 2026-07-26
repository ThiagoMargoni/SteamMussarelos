from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.debug_mode import set_local_assets
from src.utils.admin import ensure_admin

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--local",
        "--debug",
        action="store_true",
        dest="local",
        help="Usa data/games.json e icons/ locais (sem baixar do GitHub).",
    )
    return parser.parse_args(argv)

def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    set_local_assets(args.local)
    ensure_admin()

    from src.ui.main_window import MainWindow

    app = MainWindow()
    if args.local:
        app.title("Steam dos Mussarelos [LOCAL]")
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()

if __name__ == "__main__":
    # python main.py --local
    main()
