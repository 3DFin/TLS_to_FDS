"""Theme Manager for TLS_to_FDS.

Provides built-in QSS stylesheets (Dark, Light, Forest Green, System Native)
without external third-party dependencies.
"""

DARK_THEME = """
/* Base Window & Widgets */
QWidget {
    background-color: #1e1e24;
    color: #e0e0e0;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 10pt;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #33333d;
    background-color: #1e1e24;
}

QTabBar::tab {
    background: #282830;
    color: #b0b0b0;
    padding: 8px 16px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #1e1e24;
    color: #4caf50;
    font-weight: bold;
    border-bottom: 2px solid #4caf50;
}

QTabBar::tab:hover {
    background: #32323e;
    color: #ffffff;
}

/* Group Boxes */
QGroupBox {
    font-weight: bold;
    border: 1px solid #3a3a46;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 12px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: #81c784;
}

/* Inputs & Controls */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #2b2b36;
    color: #ffffff;
    border: 1px solid #444454;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 22px;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #4caf50;
}

QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled, QLabel:disabled {
    background-color: #1a1a20;
    color: #666675;
    border-color: #2c2c36;
}

/* Buttons */
QPushButton {
    background-color: #2e303d;
    color: #ffffff;
    border: 1px solid #454859;
    border-radius: 4px;
    padding: 6px 12px;
}

QPushButton:hover {
    background-color: #3d4052;
}

QPushButton:pressed {
    background-color: #1f2029;
}

QPushButton:disabled {
    background-color: #1a1a20;
    color: #555566;
    border-color: #252530;
}

QPushButton#btn_generate {
    background-color: #2e7d32;
    color: white;
    font-weight: bold;
    font-size: 11pt;
    padding: 8px;
    border-radius: 6px;
    border: none;
}

QPushButton#btn_generate:hover {
    background-color: #388e3c;
}

QPushButton#btn_generate:disabled {
    background-color: #2a382b;
    color: #667767;
}

/* Progress Bar */
QProgressBar {
    border: 1px solid #3a3a46;
    border-radius: 4px;
    text-align: center;
    color: white;
    font-weight: bold;
    background-color: #2b2b36;
}

QProgressBar::chunk {
    background-color: #2e7d32;
    border-radius: 3px;
}

/* Console Text Edit */
QTextEdit#text_console, QTextBrowser {
    background-color: #0d0e12;
    color: #d4d4d4;
    border: 1px solid #2a2a35;
    border-radius: 4px;
}

/* Scrollbars */
QScrollBar:vertical {
    background: #1e1e24;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #3a3a46;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #505060;
}

/* Tables */
QTableWidget {
    background-color: #252530;
    gridline-color: #383848;
    border: 1px solid #383848;
    border-radius: 4px;
}

QHeaderView::section {
    background-color: #1e1e24;
    color: #81c784;
    padding: 4px;
    font-weight: bold;
    border: 1px solid #383848;
}

/* Menu Bar */
QMenuBar {
    background-color: #1a1a20;
    color: #d0d0d0;
}

QMenuBar::item:selected {
    background-color: #2e7d32;
    color: #ffffff;
}

QMenu {
    background-color: #252530;
    color: #ffffff;
    border: 1px solid #3a3a46;
}

QMenu::item:selected {
    background-color: #2e7d32;
}
"""

LIGHT_THEME = """
/* Base Window & Widgets */
QWidget {
    background-color: #f8f9fa;
    color: #212529;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 10pt;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #dee2e6;
    background-color: #ffffff;
}

QTabBar::tab {
    background: #e9ecef;
    color: #495057;
    padding: 8px 16px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #ffffff;
    color: #2e7d32;
    font-weight: bold;
    border-bottom: 2px solid #2e7d32;
}

QTabBar::tab:hover {
    background: #f1f3f5;
    color: #212529;
}

/* Group Boxes */
QGroupBox {
    font-weight: bold;
    border: 1px solid #ced4da;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 12px;
    background-color: #ffffff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: #2e7d32;
}

/* Inputs & Controls */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #ffffff;
    color: #212529;
    border: 1px solid #ced4da;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 22px;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #2e7d32;
}

QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled, QLabel:disabled {
    background-color: #e9ecef;
    color: #adb5bd;
    border-color: #dee2e6;
}

/* Buttons */
QPushButton {
    background-color: #f1f3f5;
    color: #212529;
    border: 1px solid #ced4da;
    border-radius: 4px;
    padding: 6px 12px;
}

QPushButton:hover {
    background-color: #e9ecef;
}

QPushButton:pressed {
    background-color: #dee2e6;
}

QPushButton:disabled {
    background-color: #e9ecef;
    color: #adb5bd;
    border-color: #dee2e6;
}

QPushButton#btn_generate {
    background-color: #2e7d32;
    color: white;
    font-weight: bold;
    font-size: 11pt;
    padding: 8px;
    border-radius: 6px;
    border: none;
}

QPushButton#btn_generate:hover {
    background-color: #388e3c;
}

QPushButton#btn_generate:disabled {
    background-color: #a5d6a7;
    color: #ffffff;
}

/* Progress Bar */
QProgressBar {
    border: 1px solid #ced4da;
    border-radius: 4px;
    text-align: center;
    color: #212529;
    font-weight: bold;
    background-color: #e9ecef;
}

QProgressBar::chunk {
    background-color: #2e7d32;
    border-radius: 3px;
}

/* Console Text Edit */
QTextEdit#text_console, QTextBrowser {
    background-color: #1e1e1e;
    color: #d4d4d4;
    border: 1px solid #ced4da;
    border-radius: 4px;
}

/* Tables */
QTableWidget {
    background-color: #ffffff;
    gridline-color: #dee2e6;
    border: 1px solid #ced4da;
    border-radius: 4px;
}

QHeaderView::section {
    background-color: #e9ecef;
    color: #2e7d32;
    padding: 4px;
    font-weight: bold;
    border: 1px solid #dee2e6;
}

/* Menu Bar */
QMenuBar {
    background-color: #e9ecef;
    color: #212529;
}

QMenuBar::item:selected {
    background-color: #2e7d32;
    color: #ffffff;
}

QMenu {
    background-color: #ffffff;
    color: #212529;
    border: 1px solid #ced4da;
}

QMenu::item:selected {
    background-color: #2e7d32;
    color: #ffffff;
}
"""

FOREST_THEME = """
/* Base Window & Widgets */
QWidget {
    background-color: #0f1c18;
    color: #d8ece4;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 10pt;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #1f3830;
    background-color: #0f1c18;
}

QTabBar::tab {
    background: #172a24;
    color: #92b8a8;
    padding: 8px 16px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #0f1c18;
    color: #66bb6a;
    font-weight: bold;
    border-bottom: 2px solid #66bb6a;
}

QTabBar::tab:hover {
    background: #1f3a32;
    color: #ffffff;
}

/* Group Boxes */
QGroupBox {
    font-weight: bold;
    border: 1px solid #23453a;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 12px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: #81c784;
}

/* Inputs & Controls */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #172a24;
    color: #ffffff;
    border: 1px solid #295245;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 22px;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #66bb6a;
}

QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled, QLabel:disabled {
    background-color: #0d1714;
    color: #4b6a5e;
    border-color: #1c362d;
}

/* Buttons */
QPushButton {
    background-color: #1e3830;
    color: #ffffff;
    border: 1px solid #2f594d;
    border-radius: 4px;
    padding: 6px 12px;
}

QPushButton:hover {
    background-color: #274c41;
}

QPushButton:pressed {
    background-color: #12241f;
}

QPushButton#btn_generate {
    background-color: #2e7d32;
    color: white;
    font-weight: bold;
    font-size: 11pt;
    padding: 8px;
    border-radius: 6px;
    border: none;
}

QPushButton#btn_generate:hover {
    background-color: #388e3c;
}

/* Console Text Edit */
QTextEdit#text_console, QTextBrowser {
    background-color: #08100e;
    color: #c0ded2;
    border: 1px solid #1c362d;
    border-radius: 4px;
}

/* Tables */
QTableWidget {
    background-color: #14241f;
    gridline-color: #214037;
    border: 1px solid #214037;
    border-radius: 4px;
}

QHeaderView::section {
    background-color: #0f1c18;
    color: #81c784;
    padding: 4px;
    font-weight: bold;
    border: 1px solid #214037;
}

/* Menu Bar */
QMenuBar {
    background-color: #0a1411;
    color: #c0ded2;
}

QMenuBar::item:selected {
    background-color: #2e7d32;
    color: #ffffff;
}

QMenu {
    background-color: #14241f;
    color: #ffffff;
    border: 1px solid #23453a;
}

QMenu::item:selected {
    background-color: #2e7d32;
}
"""

FIRE_SMOKE_THEME = """
/* Base Window & Widgets - Smoke Gray Background & Fiery Text */
QWidget {
    background-color: #26272b;
    color: #e5e7eb;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 10pt;
}

/* Tabs */
QTabWidget::pane {
    border: 1px solid #3c3e45;
    background-color: #26272b;
}

QTabBar::tab {
    background: #1c1d21;
    color: #a0a4b0;
    padding: 8px 16px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #26272b;
    color: #ff7043;
    font-weight: bold;
    border-bottom: 2px solid #ff5722;
}

QTabBar::tab:hover {
    background: #33353b;
    color: #ffffff;
}

/* Group Boxes */
QGroupBox {
    font-weight: bold;
    border: 1px solid #484b54;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 12px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: #ff8a65;
}

/* Inputs & Controls */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #1a1b1e;
    color: #ffffff;
    border: 1px solid #4a4d57;
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 22px;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #ff7043;
}

QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled, QLabel:disabled {
    background-color: #141517;
    color: #5c5f6b;
    border-color: #2c2e36;
}

/* Buttons */
QPushButton {
    background-color: #34363d;
    color: #ffffff;
    border: 1px solid #4f525d;
    border-radius: 4px;
    padding: 6px 12px;
}

QPushButton:hover {
    background-color: #43464f;
}

QPushButton:pressed {
    background-color: #222328;
}

QPushButton#btn_generate {
    background-color: #d84315;
    color: white;
    font-weight: bold;
    font-size: 11pt;
    padding: 8px;
    border-radius: 6px;
    border: none;
}

QPushButton#btn_generate:hover {
    background-color: #f4511e;
}

QPushButton#btn_generate:disabled {
    background-color: #4e2619;
    color: #7d594f;
}

/* Progress Bar */
QProgressBar {
    border: 1px solid #444750;
    border-radius: 4px;
    text-align: center;
    color: white;
    font-weight: bold;
    background-color: #1a1b1e;
}

QProgressBar::chunk {
    background-color: #e65100;
    border-radius: 3px;
}

/* Console Text Edit */
QTextEdit#text_console, QTextBrowser {
    background-color: #121315;
    color: #f5f5f5;
    border: 1px solid #32343a;
    border-radius: 4px;
}

/* Tables */
QTableWidget {
    background-color: #1d1e22;
    gridline-color: #383a42;
    border: 1px solid #383a42;
    border-radius: 4px;
}

QHeaderView::section {
    background-color: #161719;
    color: #ff8a65;
    padding: 4px;
    font-weight: bold;
    border: 1px solid #383a42;
}

/* Menu Bar */
QMenuBar {
    background-color: #18191c;
    color: #e0e2e5;
}

QMenuBar::item:selected {
    background-color: #d84315;
    color: #ffffff;
}

QMenu {
    background-color: #202125;
    color: #ffffff;
    border: 1px solid #3c3e45;
}

QMenu::item:selected {
    background-color: #d84315;
}
"""

SYSTEM_THEME = ""

THEMES: dict[str, str] = {
    "Dark": DARK_THEME,
    "Light": LIGHT_THEME,
    "Forest Green": FOREST_THEME,
    "Fire & Smoke": FIRE_SMOKE_THEME,
    "System Native": SYSTEM_THEME,
}


def apply_theme(window_widget, theme_name: str = "Dark") -> str:
    """Applies the selected QSS theme to the target QWidget / QMainWindow."""
    stylesheet = THEMES.get(theme_name, DARK_THEME)
    window_widget.setStyleSheet(stylesheet)
    return theme_name
