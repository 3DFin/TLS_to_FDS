import sys
from PySide6.QtWidgets import QApplication
import pytest

from tls_to_fds.gui import TLS_to_FDS_GUI


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


def test_gui_restart_controls_toggle(qapp):
    gui = TLS_to_FDS_GUI()
    # By default restart_active is False
    gui.ui.check_restart_active.setChecked(False)
    assert gui.ui.spin_dt_restart.isEnabled() is False
    assert gui.ui.lbl_dt_restart.isEnabled() is False

    # Toggle to True
    gui.ui.check_restart_active.setChecked(True)
    assert gui.ui.spin_dt_restart.isEnabled() is True
    assert gui.ui.lbl_dt_restart.isEnabled() is True


def test_gui_litter_model_stacked_visibility(qapp):
    gui = TLS_to_FDS_GUI()
    gui.ui.check_litter.setChecked(True)

    # Uniform mode: neither Model 1 nor Model 2 box should be visible (isHidden is True)
    gui.ui.combo_litter_model.setCurrentText("Uniform (Default)")
    assert gui.ui.groupBox_7.isHidden() is True
    assert gui.ui.groupBox_8.isHidden() is True

    # Model 1 mode: Model 1 box visible (isHidden False), Model 2 box hidden
    gui.ui.combo_litter_model.setCurrentText("Model 1: Tree map and Distance Decay")
    assert gui.ui.groupBox_7.isHidden() is False
    assert gui.ui.groupBox_8.isHidden() is True

    # Model 2 mode: Model 2 box visible, Model 1 box hidden
    gui.ui.combo_litter_model.setCurrentText("Model 2: Canopy Turnover and Fall Dispersion")
    assert gui.ui.groupBox_7.isHidden() is True
    assert gui.ui.groupBox_8.isHidden() is False

    # If litter checkbox is disabled, both should hide
    gui.ui.check_litter.setChecked(False)
    assert gui.ui.groupBox_7.isHidden() is True
    assert gui.ui.groupBox_8.isHidden() is True


def test_gui_dtm_button_enabled_states(qapp):
    gui = TLS_to_FDS_GUI()
    gui.ui.check_litter.setChecked(True)

    # Uniform mode: DTM controls disabled
    gui.ui.combo_litter_model.setCurrentText("Uniform (Default)")
    assert gui.ui.btn_dtm_path.isEnabled() is False

    # Model 1 mode: DTM controls enabled
    gui.ui.combo_litter_model.setCurrentText("Model 1: Tree map and Distance Decay")
    assert gui.ui.btn_dtm_path.isEnabled() is True


def test_theme_switching(qapp):
    gui = TLS_to_FDS_GUI()
    gui.change_theme("Light")
    assert gui.current_theme == "Light"
    assert "background-color: #f8f9fa" in gui.ui.styleSheet()

    gui.change_theme("Forest Green")
    assert gui.current_theme == "Forest Green"
    assert "background-color: #0f1c18" in gui.ui.styleSheet()

    gui.change_theme("Fire & Smoke")
    assert gui.current_theme == "Fire & Smoke"
    assert "background-color: #26272b" in gui.ui.styleSheet()

    gui.change_theme("Dark")
    assert gui.current_theme == "Dark"
    assert "background-color: #1e1e24" in gui.ui.styleSheet()
