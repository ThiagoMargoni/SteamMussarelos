from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.debug_mode import install_excepthook, log, set_local_assets
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
    if args.local:
        install_excepthook()
        from src.core.settings import app_data_dir

        log("info", "boot --local", cwd=str(ROOT), appdata=str(app_data_dir()))

    from PySide6.QtWidgets import QApplication

    from src.core.single_instance import SingleInstance
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

    guard = SingleInstance(app)
    if guard.activate_existing():
        log("info", "instancia existente encontrada; saindo")
        sys.exit(0)

    ensure_admin()

    if not guard.start_server():
        log("info", "nao foi possivel iniciar single-instance server; saindo")
        sys.exit(0)

    window = MainWindow()
    guard.activated.connect(window.restore_from_background)
    if args.local:
        window.setWindowTitle("Steam dos Mussarelos [LOCAL]")
        from src.core.debug_mode import log_path

        log("info", "janela pronta", log_file=str(log_path()))
    window.show()
    code = app.exec()
    log("info", "app encerrado", code=code)
    sys.exit(code)

if __name__ == "__main__":
    main()
