import sys
import os
from pathlib import Path

# Redirect stdout/stderr to os.devnull if they are None (PyInstaller --noconsole)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# Add the 'src' directory to the Python path so local modules can be found
sys.path.insert(0, str(Path(__file__).parent / "src"))

from PySide6.QtWidgets import QApplication
from tls_to_fds.gui import TLS_to_FDS_GUI


def main():
    app = QApplication(sys.argv)

    window = TLS_to_FDS_GUI()
    window.ui.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
