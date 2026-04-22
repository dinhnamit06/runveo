from __future__ import annotations
import sys
import os
from pathlib import Path

def _ensure_project_root() -> None:
    if getattr(sys, 'frozen', False):
        # In PyInstaller, the libs are in _internal or the exe dir
        ext_path = Path(sys._MEIPASS).resolve()
        if str(ext_path) not in sys.path:
            sys.path.insert(0, str(ext_path))
    else:
        root = Path(__file__).resolve().parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))

# Call it BEFORE any other imports that might fail
_ensure_project_root()

from branding_config import APP_VERSION, WINDOW_TITLE
import License

def main() -> None:
    print(f'[RUNNER] Start launcher for {WINDOW_TITLE} - {APP_VERSION}')
    License.main()

if __name__ == '__main__':
    main()