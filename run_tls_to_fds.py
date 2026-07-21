import sys
from pathlib import Path

# Add the 'src' directory to the Python path so local modules can be found
sys.path.insert(0, str(Path(__file__).parent / "src"))

from PySide6.QtWidgets import QApplication
import qdarktheme
from tls_to_fds.gui import TLS_to_FDS_GUI

def main():
    app = QApplication(sys.argv)
    qdarktheme.setup_theme()
    
    window = TLS_to_FDS_GUI()
    window.ui.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
