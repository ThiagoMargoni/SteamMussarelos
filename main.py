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
    parser.add_argument(
        "--apply-update",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--update-target",
        default="",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--update-pid",
        type=int,
        default=0,
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv)

def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    if args.apply_update:
        ensure_admin()
        from src.core.updater import run_apply_update

        target = Path(args.update_target) if args.update_target else None
        if target is None or not args.update_pid:
            sys.exit(2)
        sys.exit(run_apply_update(target, args.update_pid))

    set_local_assets(args.local)
    ensure_admin()

    from PySide6.QtWidgets import QApplication

    from src.ui.main_window import MainWindow
    from src.ui.theme import app_stylesheet, font_body
    from src.utils.paths import resolve_resource

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(font_body())
    app.setStyleSheet(app_stylesheet())
    icon = resolve_resource("assets", "app.ico")
    if icon:
        from PySide6.QtGui import QIcon

        app.setWindowIcon(QIcon(str(icon.resolve())))

    window = MainWindow()
    if args.local:
        window.setWindowTitle("Steam dos Mussarelos [LOCAL]")
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
