import sys
from pathlib import Path

import laspy
from PySide6.QtCore import QFile, QUrl
from PySide6.QtGui import QAction, QActionGroup, QFont, QPixmap
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHeaderView,
    QLabel,
    QMessageBox,
    QStyle,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtWebEngineCore import QWebEngineSettings
    from PySide6.QtWebEngineWidgets import QWebEngineView

    WEB_ENGINE_AVAILABLE = True
except ImportError:
    WEB_ENGINE_AVAILABLE = False

from tls_to_fds import __version__, io_utils, theme_manager
from tls_to_fds.constants import TOOLTIPS, WELCOME_BANNER
from tls_to_fds.models import (
    DomainParams,
    EnvParams,
    GroundFuels,
    OutputParams,
    RuntimeConfig,
)
from tls_to_fds.workers import PipelineWorker


class TLS_to_FDS_GUI:
    def __init__(self):
        super().__init__()

        # 1. Load the UI File generated from Qt Creator
        ui_file_path = Path(__file__).parent / "mainwindow.ui"
        ui_file = QFile(str(ui_file_path))
        if not ui_file.open(QFile.ReadOnly):
            print(f"Cannot open {ui_file_path}")
            sys.exit(-1)

        loader = QUiLoader()
        self.ui = loader.load(ui_file)
        ui_file.close()

        # Make the UI the central widget of this window
        self.ui.setWindowTitle(
            "TLS_to_FDS - FDS inputs from Ground-Based Forest Point Clouds"
        )
        self.ui.resize(1250, 980)

        # Inject the About Tab content dynamically
        self.setup_about_tab()

        # Aesthetic: Set standard icons for buttons
        style = self.ui.style()
        self.ui.btn_browse_input.setIcon(
            style.standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        )
        self.ui.btn_browse_output.setIcon(
            style.standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        )
        self.ui.btn_add_layer.setIcon(
            style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        )
        self.ui.btn_remove_layer.setIcon(
            style.standardIcon(QStyle.StandardPixmap.SP_TrashIcon)
        )
        self.ui.btn_generate.setIcon(
            style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )

        # Theme: Apply built-in theme
        self.current_theme = "Dark"
        theme_manager.apply_theme(self.ui, self.current_theme)
        self.setup_theme_menu()

        # Aesthetic: Make the console look like a true terminal
        console_font = QFont("Consolas", 10)  # Monospace font
        self.ui.text_console.setFont(console_font)

        # Aesthetic: insert forest schematic into the GUI
        if hasattr(self.ui, "lbl_forest_schematic"):
            image_path = Path(__file__).parent / "fig_fuel_layers_lbls.png"
            if image_path.exists():
                pixmap = QPixmap(str(image_path))
                self.ui.lbl_forest_schematic.setPixmap(pixmap)

        # Reset progress bar just in case
        if hasattr(self.ui, "progress_bar"):
            self.ui.progress_bar.setValue(0)

        # 2. Wire Up Directory Selection Signals
        self.ui.btn_browse_input.clicked.connect(self.browse_input_dir)
        self.ui.btn_browse_output.clicked.connect(self.browse_output_dir)

        # --- Wire Up Dynamic Ground Fuel Toggling
        if hasattr(self.ui, "check_litter"):
            self.ui.check_litter.toggled.connect(self.update_litter_model_visibility)

        # 3. Wire Up Table Manipulation Signals
        self.ui.btn_add_layer.clicked.connect(self.add_layer_row)
        self.ui.btn_remove_layer.clicked.connect(self.remove_layer_row)

        # Configure Table Columns
        self.ui.table_fuel_layers.setColumnCount(7)
        self.ui.table_fuel_layers.setHorizontalHeaderLabels(
            [
                "Filename",
                "Fuel Class",
                "Bulk Density",
                "Moisture",
                "S/V Ratio",
                "Length (m)",
                "Drag",
            ]
        )

        header = self.ui.table_fuel_layers.horizontalHeader()
        for i in range(0, 7):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        # 4. Apply External Tooltips
        for widget_name, tooltip_text in TOOLTIPS.items():
            widget = getattr(self.ui, widget_name, None)
            if widget:
                widget.setToolTip(tooltip_text)

        # 5. Connect ember and restart checkbox signals directly to spin boxes' enabled state
        self.ui.check_track_embers.toggled.connect(
            self.ui.spin_ember_density.setEnabled
        )
        self.ui.check_track_embers.toggled.connect(
            self.ui.spin_ember_velocity.setEnabled
        )
        if hasattr(self.ui, "check_restart_active"):
            if hasattr(self.ui, "spin_dt_restart"):
                self.ui.check_restart_active.toggled.connect(
                    self.ui.spin_dt_restart.setEnabled
                )
            if hasattr(self.ui, "lbl_dt_restart"):
                self.ui.check_restart_active.toggled.connect(
                    self.ui.lbl_dt_restart.setEnabled
                )

        # 6. Trigger initial control states manually so they start correctly on launch
        initial_embers = self.ui.check_track_embers.isChecked()
        self.ui.spin_ember_density.setEnabled(initial_embers)
        self.ui.spin_ember_velocity.setEnabled(initial_embers)

        if hasattr(self.ui, "check_restart_active"):
            initial_restart = self.ui.check_restart_active.isChecked()
            if hasattr(self.ui, "spin_dt_restart"):
                self.ui.spin_dt_restart.setEnabled(initial_restart)
            if hasattr(self.ui, "lbl_dt_restart"):
                self.ui.lbl_dt_restart.setEnabled(initial_restart)

        # 7. Wire Up Execution Pipeline
        self.ui.btn_generate.clicked.connect(self.generate_fds)

        # 8. Set Defaults
        self._apply_default_config()

    def _apply_default_config(self):
        from tls_to_fds.io_utils import get_default

        # Domain Params
        self.ui.spin_lateral_pad.setValue(
            get_default("domain_params", "lateral_pad", 10.0)
        )
        self.ui.spin_top_pad.setValue(get_default("domain_params", "top_pad", 20.0))
        self.ui.spin_mpi_x.setValue(get_default("domain_params", "mpi_x", 2))
        self.ui.spin_mpi_y.setValue(get_default("domain_params", "mpi_y", 3))

        # Env Params
        self.ui.spin_sim_time.setValue(get_default("env_params", "sim_time", 240.0))
        self.ui.spin_wind_dev.setValue(get_default("env_params", "wind_dev_time", 15.0))
        self.ui.spin_wind_dir.setValue(get_default("env_params", "wind_dir", 15.0))
        self.ui.spin_wind_speed.setValue(get_default("env_params", "wind_speed", 3.0))
        self.ui.spin_hrrpua.setValue(get_default("env_params", "hrrpua", 500.0))
        self.ui.spin_ember_density.setValue(
            get_default("env_params", "ember_density", 62.5)
        )
        self.ui.spin_ember_velocity.setValue(
            get_default("env_params", "ember_velocity", 0.0)
        )
        self.ui.spin_ign_duration.setValue(
            get_default("env_params", "ign_duration", 30.0)
        )
        self.ui.spin_vent_width.setValue(get_default("env_params", "vent_width", 1.0))
        self.ui.spin_obukhov.setValue(get_default("env_params", "obukhov", -350.0))
        self.ui.spin_z0.setValue(get_default("env_params", "z0", 0.5))

        # Ground Fuels (Litter)
        if hasattr(self.ui, "spin_litter_depth"):
            self.ui.spin_litter_depth.setValue(
                get_default("ground_fuels", "litter_depth", 0.05)
            )
        if hasattr(self.ui, "spin_litter_bd"):
            self.ui.spin_litter_bd.setValue(
                get_default("ground_fuels", "litter_bd", 15.0)
            )
        if hasattr(self.ui, "spin_litter_moisture"):
            self.ui.spin_litter_moisture.setValue(
                get_default("ground_fuels", "litter_moisture", 0.1)
            )

        # Litter Models Wiring
        if hasattr(self.ui, "btn_browse_tree_map"):
            self.ui.btn_browse_tree_map.clicked.connect(self.browse_tree_map)
        if hasattr(self.ui, "btn_dtm_path"):
            self.ui.btn_dtm_path.clicked.connect(self.browse_dtm)
        if hasattr(self.ui, "btn_browse_dtm"):
            self.ui.btn_browse_dtm.clicked.connect(self.browse_dtm)
        if hasattr(self.ui, "combo_litter_model"):
            self.ui.combo_litter_model.currentTextChanged.connect(
                self.update_litter_model_visibility
            )
            self.update_litter_model_visibility()

        # Runtime Config
        self.ui.spin_voxel_size.setValue(
            get_default("runtime_config", "voxel_size", 0.2)
        )

        # Embedded 3D Mesh Alignment Visualizer
        self.web_view = None
        self.setup_embedded_visualizer()

        # Wire up spatial signals for live 3D preview synchronization
        self.ui.spin_lateral_pad.valueChanged.connect(self.update_embedded_3d_view)
        self.ui.spin_top_pad.valueChanged.connect(self.update_embedded_3d_view)
        self.ui.spin_voxel_size.valueChanged.connect(self.update_embedded_3d_view)
        self.ui.combo_sky_mult.currentTextChanged.connect(self.update_embedded_3d_view)
        self.ui.spin_mpi_x.valueChanged.connect(self.update_embedded_3d_view)
        self.ui.spin_mpi_y.valueChanged.connect(self.update_embedded_3d_view)
        if hasattr(self.ui, "btn_wizard"):
            self.ui.btn_wizard.clicked.connect(self.update_embedded_3d_view)

        # 8. Print the Welcome Banner
        self.log(WELCOME_BANNER)

        # 9. Initialize dynamic preset data
        self.populate_presets()

        # Auto-update densities if the global preset is changed ---
        self.ui.combo_preset.currentTextChanged.connect(
            self.update_preset_tooltip_and_rows
        )

    def log(self, message):
        """Appends status updates safely into the embedded GUI text terminal."""
        self.ui.text_console.append(str(message))
        # Autoscroll to the bottom
        self.ui.text_console.ensureCursorVisible()

    def browse_tree_map(self):
        """Opens file dialog to select a 3DFin tree map file."""
        filename, _ = QFileDialog.getOpenFileName(
            self.ui,
            "Select 3DFin Tree Map File",
            "",
            "Tree Maps (*.csv *.txt *.las *.laz);;All Files (*)",
        )
        if filename and hasattr(self.ui, "line_tree_map_path"):
            self.ui.line_tree_map_path.setText(filename)

    def browse_dtm(self):
        """Opens file dialog to select a 3DFin DTM file."""
        filename, _ = QFileDialog.getOpenFileName(
            self.ui,
            "Select 3DFin DTM Surface File",
            "",
            "DTM Files (*.obj *.csv *.txt *.asc *.xyz *.las *.laz);;All Files (*)",
        )
        if filename and hasattr(self.ui, "line_dtm_path"):
            self.ui.line_dtm_path.setText(filename)

    def update_litter_model_visibility(self):
        """Enables/disables litter parameters based on model selection (Path 1 UI state machine)."""
        litter_active = (
            self.ui.check_litter.isChecked()
            if hasattr(self.ui, "check_litter")
            else True
        )

        # Toggle main model combo box
        if hasattr(self.ui, "combo_litter_model"):
            self.ui.combo_litter_model.setEnabled(litter_active)

        if not hasattr(self.ui, "combo_litter_model"):
            return

        mode = self.ui.combo_litter_model.currentText()

        # Determine model modes
        # is_uniform = "Uniform" in mode
        is_model_1 = "Model 1" in mode
        is_model_2 = "Model 2" in mode

        # Toggle visibility of Model 1 and Model 2 parameter group boxes
        if hasattr(self.ui, "groupBox_7"):
            self.ui.groupBox_7.setVisible(is_model_1 and litter_active)
        if hasattr(self.ui, "groupBox_8"):
            self.ui.groupBox_8.setVisible(is_model_2 and litter_active)

        # Helper lambda to set enabled status safely
        def set_controls_enabled(attrs, enabled):
            for attr in attrs:
                if hasattr(self.ui, attr):
                    getattr(self.ui, attr).setEnabled(enabled and litter_active)

        # Basic Litter Parameters
        # Model 1 uses baseline BD + depth. Model 2 calculates BD from canopy turnover.
        set_controls_enabled(["lbl_layer_depth", "spin_litter_depth"], not is_model_1)
        set_controls_enabled(["lbl_layer_bd", "spin_litter_bd"], not is_model_2)
        set_controls_enabled(["lbl_layer_moisture", "spin_litter_moisture"], True)

        # Model 1 Parameters (Tree map & decay)
        set_controls_enabled(
            [
                "line_tree_map_path",
                "btn_browse_tree_map",
                "lbl_decay_alpha",
                "spin_decay_alpha",
                "lbl_min_litter_bd",
                "spin_min_litter_bd",
            ],
            is_model_1,
        )

        # Model 2 Parameters (Canopy turnover)
        set_controls_enabled(
            [
                "lbl_turnover_rate",
                "spin_turnover_rate",
                "lbl_accumulation_years",
                "spin_accumulation_years",
                "lbl_dispersion_sigma",
                "spin_dispersion_sigma",
            ],
            is_model_2,
        )

        # DTM Controls (Enabled for any dynamic model)
        set_controls_enabled(
            ["line_dtm_path", "btn_dtm_path", "btn_browse_dtm"],
            is_model_1 or is_model_2,
        )

    def calculate_global_forest_width(self):
        """Instantly reads LAS headers without loading points to find the global footprint."""
        input_dir = Path(self.ui.line_input_dir.text().strip())
        if not input_dir.exists():
            return None

        global_min_x, global_min_y = float("inf"), float("inf")
        global_max_x, global_max_y = float("-inf"), float("-inf")
        valid_files = 0

        for row in range(self.ui.table_fuel_layers.rowCount()):
            filename = self.ui.table_fuel_layers.item(row, 0).text()
            filepath = input_dir / filename

            if filepath.exists():
                try:
                    # laspy.open() reads ONLY the metadata header
                    with laspy.open(filepath) as f:
                        hdr = f.header
                        global_min_x = min(global_min_x, hdr.x_min)
                        global_max_x = max(global_max_x, hdr.x_max)
                        global_min_y = min(global_min_y, hdr.y_min)
                        global_max_y = max(global_max_y, hdr.y_max)
                        valid_files += 1
                except Exception as e:
                    self.log(
                        f"<span style='color: #ef5350;'>Warning: Could not read header of {filename} - {e}</span>"
                    )

        if valid_files == 0:
            return None

        width_x = global_max_x - global_min_x
        width_y = global_max_y - global_min_y
        return max(width_x, width_y)  # Visualizer MVP uses largest dimension

    def setup_embedded_visualizer(self):
        """Instantiates QWebEngineView directly inside tab_spatial's container_3d_view."""
        if not hasattr(self.ui, "container_3d_view"):
            return

        layout = QVBoxLayout(self.ui.container_3d_view)
        layout.setContentsMargins(0, 0, 0, 0)

        if not WEB_ENGINE_AVAILABLE:
            fallback = QLabel(
                "<div style='text-align:center; padding:60px; color:#aaa; font-family:sans-serif;'>"
                "<h3 style='color:#e57373;'>3D Visualizer Standby</h3>"
                "<p>Install <b>PySide6-WebEngine</b> to view live 3D mesh previewing:<br><br>"
                "<code>pip install PySide6-WebEngine</code></p></div>"
            )
            layout.addWidget(fallback)
            return

        html_path = (Path(__file__).parent / "mesh_visualizer.html").resolve()
        if not html_path.exists():
            fallback = QLabel("<h3 style='color:red; text-align:center;'>mesh_visualizer.html not found.</h3>")
            layout.addWidget(fallback)
            return

        self.web_view = QWebEngineView()
        self.web_view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        self.web_view.setUrl(QUrl.fromLocalFile(str(html_path)))
        layout.addWidget(self.web_view)

        # Sync initial parameters once WebEngine loads
        self.web_view.loadFinished.connect(lambda ok: self.update_embedded_3d_view())

    def update_embedded_3d_view(self):
        """Pushes current GUI spinbox values live into the embedded 3D Three.js canvas."""
        if not self.web_view or not WEB_ENGINE_AVAILABLE:
            return

        forest_width = self.calculate_global_forest_width() or 40.0
        pad = self.ui.spin_lateral_pad.value()
        top_pad = self.ui.spin_top_pad.value()
        vox = self.ui.spin_voxel_size.value()

        sky_text = self.ui.combo_sky_mult.currentText().replace("x", "")
        mult = int(sky_text) if sky_text else 2
        mpi_x = self.ui.spin_mpi_x.value()
        mpi_y = self.ui.spin_mpi_y.value()

        js = f"""
        if (typeof updateVisualization === 'function' && typeof THREE !== 'undefined') {{
            document.getElementById('slider-forest').value = {forest_width};
            document.getElementById('slider-forest').disabled = true;
            document.getElementById('slider-pad').value = {pad};
            document.getElementById('slider-top-pad').value = {top_pad};
            document.getElementById('slider-voxel').value = {vox};
            document.getElementById('slider-mult').value = {mult};
            document.getElementById('slider-mpi-x').value = {mpi_x};
            document.getElementById('slider-mpi-y').value = {mpi_y};
            updateVisualization();
        }}
        """
        self.web_view.page().runJavaScript(js)

    def browse_input_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self.ui, "Select Input Point Clouds Directory"
        )
        if directory:
            self.ui.line_input_dir.setText(directory)
            self.log(f"Input source changed to: {directory}")

    def browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self.ui, "Select FDS Output Target Directory"
        )
        if directory:
            self.ui.line_output_dir.setText(directory)
            self.log(f"Output targets changed to: {directory}")

    def populate_presets(self):
        """Scans the presets directory and populates the dropdown menu."""
        preset_dir = io_utils.get_presets_dir()
        # Create the folder if it doesn't exist yet to prevent crashes
        preset_dir.mkdir(exist_ok=True)

        self.ui.combo_preset.clear()

        # Find all .json files and get just their names (without the .json extension)
        presets = [f.stem for f in preset_dir.glob("*.json")]

        if presets:
            self.ui.combo_preset.addItems(presets)
            self.log(f"Loaded {len(presets)} forest presets.")
        else:
            self.ui.combo_preset.addItem("No forest presets found")
            self.log("Warning: No JSON presets found in the 'presets/' folder.")

    def update_preset_tooltip_and_rows(self, preset_name):
        """Updates the dropdown tooltip and forces all table rows to refresh their defaults."""
        if preset_name and preset_name != "No forest presets found":
            try:
                preset_data = io_utils.load_preset(preset_name)
                # Apply the description as a hover tooltip!
                desc = preset_data.get("description", "No description provided.")
                self.ui.combo_preset.setToolTip(desc)
            except Exception:
                self.ui.combo_preset.setToolTip("Error loading preset.")

        # Refresh all rows
        for row in range(self.ui.table_fuel_layers.rowCount()):
            combo = self.ui.table_fuel_layers.cellWidget(row, 1)
            if combo:
                self.update_row_parameters(row, combo)

        # Update Synthetic Ground Fuels
        if preset_name and preset_name != "No forest presets found":
            try:
                preset_data = io_utils.load_preset(preset_name)

                if "Litter" in preset_data:
                    self.ui.spin_litter_bd.setValue(
                        preset_data["Litter"].get("default_bulk_density", 15.0)
                    )
                    self.ui.spin_litter_moisture.setValue(
                        preset_data["Litter"].get("moisture_fraction", 0.05)
                    )

                if "Duff" in preset_data:
                    self.ui.spin_duff_bd.setValue(
                        preset_data["Duff"].get("default_bulk_density", 50.0)
                    )
                    self.ui.spin_duff_moisture.setValue(
                        preset_data["Duff"].get("moisture_fraction", 0.10)
                    )

            except Exception as e:
                self.log(f"Warning: Could not read synthetic fuel properties: {e!s}")

    def update_row_parameters(self, row, combo_box):
        """Reads the JSON preset and updates BOTH density and moisture cells."""
        preset_name = self.ui.combo_preset.currentText()
        if preset_name and preset_name != "No forest presets found":
            try:
                preset_data = io_utils.load_preset(preset_name)
                semantic_class = combo_box.currentText()
                if semantic_class in preset_data:
                    props = preset_data[semantic_class]
                    self.ui.table_fuel_layers.item(row, 2).setText(
                        str(props.get("default_bulk_density", 0.8))
                    )
                    self.ui.table_fuel_layers.item(row, 3).setText(
                        str(props.get("moisture_fraction", 0.15))
                    )
                    self.ui.table_fuel_layers.item(row, 4).setText(
                        str(props.get("sv_ratio", 3588.0))
                    )
                    self.ui.table_fuel_layers.item(row, 5).setText(
                        str(props.get("length", 0.10))
                    )
                    self.ui.table_fuel_layers.item(row, 6).setText(
                        str(props.get("drag", 2.8))
                    )
            except Exception as e:
                self.log(f"Warning: Could not read preset parameters: {e!s}")

    def add_layer_row(self):
        # Open file browser restricted to point cloud types
        files, _ = QFileDialog.getOpenFileNames(
            self.ui,
            "Select Forest Fuel Layer Files",
            self.ui.line_input_dir.text(),
            "Point Clouds (*.las *.laz *.txt)",
        )

        for file_path in files:
            file_name = Path(file_path).name

            # Check if file is already in the table
            is_duplicate = False
            for row in range(self.ui.table_fuel_layers.rowCount()):
                existing_item = self.ui.table_fuel_layers.item(row, 0)
                if existing_item and existing_item.text() == file_name:
                    self.log(f"Skipping duplicate file: {file_name}")
                    is_duplicate = True
                    break

            if is_duplicate:
                continue  # Skip to the next file if this one is a duplicate
            # --------------------------------------------------------

            row_count = self.ui.table_fuel_layers.rowCount()
            self.ui.table_fuel_layers.insertRow(row_count)

            # Populate Column 0: Filename
            self.ui.table_fuel_layers.setItem(row_count, 0, QTableWidgetItem(file_name))

            # Populate Column 1: Dynamic Dropdown for Semantic Class
            combo_class = QComboBox()
            combo_class.addItems(
                [
                    "Ground Fuel",
                    "Surface Fuel",
                    "Ladder Fuel",
                    "Trunks",
                ]
            )

            # Populate Columns 2 to 6: Insert blank dummy items FIRST
            for col in range(2, 7):
                self.ui.table_fuel_layers.setItem(row_count, col, QTableWidgetItem(""))

            combo_class.currentTextChanged.connect(
                lambda text, r=row_count, cb=combo_class: self.update_row_parameters(
                    r, cb
                )
            )

            self.ui.table_fuel_layers.setCellWidget(row_count, 1, combo_class)

            # Trigger it once manually to apply the current preset's starting value
            self.update_row_parameters(row_count, combo_class)

            self.log(f"Added layer reference: {file_name}")

        self.update_embedded_3d_view()

    def remove_layer_row(self):
        current_row = self.ui.table_fuel_layers.currentRow()
        if current_row >= 0:
            self.ui.table_fuel_layers.removeRow(current_row)
            self.log(f"Removed layer config index row: {current_row}")
            self.update_embedded_3d_view()

    def setup_about_tab(self):
        """Dynamically creates and appends an About/References tab to the GUI."""
        self.tab_about = QWidget()
        layout = QVBoxLayout()

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)  # Make HTML links clickable

        html_content = f"""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; padding: 20px;">
            <h1 style="color: #2e7d32; margin-bottom: 0px;">TLS_to_FDS</h1>
            <p style="font-size: 14px; margin-top: 0px;"><b>Version {__version__}</b> | Point Cloud to Fire Simulation Pipeline</p>
            <hr>
            
            <h3>📖 Overview</h3>
            <p>TLS_to_FDS is an open-source framework designed to automate the conversion of semantically segmented ground-based point clouds (such as Terrestrial Laser Scanning) into ready-to-run input files for the Fire Dynamics Simulator (FDS).</p>
            
            <h3>👨‍🔬 Authors & Contributors</h3>
            <p>Developed by the <b>3DFin Project Team</b>. Contributions from the open-source fire modeling and forestry remote sensing community are highly encouraged.</p>
            
            <h3>🏛️ Acknowledgments & Funding</h3>
            <p style="font-size: 13px;">This work was supported by:</p>
            <ul style="font-size: 13px;">
                <li style="margin-bottom: 5px;"><b>UK NERC</b> (NE/T001194/1): <i>‘Advancing 3D Fuel Mapping for Wildfire Behaviour and Risk Mitigation Modelling’</i></li>
                <li style="margin-bottom: 5px;"><b>Spanish Knowledge Generation</b> (PID2021-126790NB-I00): <i>‘Advancing carbon emission estimations from wildfires applying artificial intelligence to 3D terrestrial point clouds’</i></li>
                <li style="margin-bottom: 5px;"><b>FSE+ & Principality of Asturias Government (Spain)</b>: Research grant <i>‘FIREPROs’</i> (IDE/2024/000780)</li>
            </ul>
            
            <h3>🔬 Scientific References & Sub-Models</h3>
            <ul>
                <li style="margin-bottom: 10px;"><b>Fire Dynamics Simulator (FDS):</b> McGrattan, K., Hostikka, S., McDermott, R., Floyd, J., Weinschenk, C., & Overholt, K. (2023). <i>Fire Dynamics Simulator User's Guide</i>. NIST Special Publication 1019.</li>
                <li style="margin-bottom: 10px;"><b>Synthetic Ground Fuel Models (Litter & Duff):</b> Implemented utilizing the FDS 1D Boundary Fuel Model (BFM) grid tiles and 3D voxelized representations:
                    <ul style="margin-top: 5px;">
                        <li><b>Uniform Model:</b> Homogeneous ground fuel layer based on biome bulk density presets.</li>
                        <li><b>Model 1 (Tree Map & Distance Decay):</b> Exponential spatial decay of litter bulk density relative to tree trunk stem locations.</li>
                        <li><b>Model 2 (Canopy Turnover & Fall Dispersion):</b> Dynamic litter fall calculated from annual canopy turnover rate (<i>k<sub>turnover</sub></i>), accumulation time (<i>T<sub>accum</sub></i>), and 2D Gaussian wind dispersion (<i>σ</i>) spatially clamped to forest boundaries.</li>
                    </ul>
                </li>
                <li style="margin-bottom: 10px;"><b>Interactive 3D Domain Alignment Engine:</b> Real-time Three.js viewport for multi-mesh boundary snapping, sky coarseness ratio validation, and MPI process grid decomposition (<i>N<sub>x</sub> × N<sub>y</sub></i>).</li>
                <li style="margin-bottom: 10px;"><b>Atmospheric Physics:</b> Stratification and boundary-layer wind profiles parameterized via Monin-Obukhov similarity theory (Obukhov Length).</li>
                <li style="margin-bottom: 10px;"><b>Firebrand Lofting & Tracking:</b> Enabled via Lagrangian particle tracking using user-defined density and velocity lofting thresholds.</li>
                <li style="margin-bottom: 10px;"><b>High-Performance Voxelization Engine:</b> Driven by the <a href="https://github.com/dendromatics/dendroptimized">dendroptimized</a> C-backend for rapid 3D grid conversion of massive LiDAR point clouds.</li>
            </ul>
            
            <h3>📄 How to Cite</h3>
            <p><i>If you use TLS_to_FDS in your research, please cite our project repository and upcoming publication. (Citation details to be updated upon final paper release).</i></p>
            
            <hr>
            <p style="color: gray; font-size: 12px;"><i>This software utilizes <b>laspy</b> for point cloud I/O, <b>dendroptimized</b> for C-accelerated spatial voxelization, <b>PySide6 / QtWebEngine</b> for the GUI, and <b>Three.js</b> for embedded 3D web visualizer previews.</i></p>
        </div>
        """
        browser.setHtml(html_content)
        layout.addWidget(browser)
        self.tab_about.setLayout(layout)

        # Add it to the existing QTabWidget found in the UI
        self.ui.tabs.addTab(self.tab_about, "About / References")

    def setup_theme_menu(self):
        """Dynamically builds the View -> Theme menu in the menubar."""
        if not hasattr(self.ui, "menubar") or self.ui.menubar is None:
            return

        view_menu = self.ui.menubar.addMenu("&View")
        theme_menu = view_menu.addMenu("&Theme")

        action_group = QActionGroup(self.ui)
        action_group.setExclusive(True)

        for theme_name in theme_manager.THEMES:
            # Escape '&' as '&&' in QAction text so Qt menu renders 'Fire & Smoke' instead of hiding '&' as an accelerator key
            action_text = theme_name.replace("&", "&&")
            action = QAction(action_text, self.ui, checkable=True)
            if theme_name == self.current_theme:
                action.setChecked(True)

            # Connect lambda with default argument to capture theme_name
            action.triggered.connect(
                lambda checked=False, name=theme_name: self.change_theme(name)
            )
            action_group.addAction(action)
            theme_menu.addAction(action)

    def change_theme(self, theme_name: str):
        """Switches the active QSS theme dynamically."""
        self.current_theme = theme_manager.apply_theme(self.ui, theme_name)
        self.log(f"Applied UI Theme: {theme_name}")

    def generate_fds(self):
        # 1. Scrape data structures out of UI input nodes
        input_dir = self.ui.line_input_dir.text().strip()
        output_dir = self.ui.line_output_dir.text().strip()
        voxel_size = self.ui.spin_voxel_size.value()
        selected_preset = self.ui.combo_preset.currentText()
        output_filename = self.ui.line_output_name.text().strip() or "model"

        try:
            # Safely extract the integer from strings like "2x", "3x"
            sky_mult_text = self.ui.combo_sky_mult.currentText().replace("x", "")
            sky_mult = int(sky_mult_text) if sky_mult_text else 2
        except Exception:
            sky_mult = 2  # Fallback safety

        # --- Pre-Flight Checks ---
        if not input_dir or not Path(input_dir).exists():
            QMessageBox.critical(
                self.ui, "Directory Error", "Please provide a valid Input Directory."
            )
            return

        if not output_dir or not Path(output_dir).exists():
            QMessageBox.critical(
                self.ui, "Directory Error", "Please provide a valid Output Directory."
            )
            return

        if self.ui.table_fuel_layers.rowCount() == 0:
            QMessageBox.warning(
                self.ui,
                "No Fuels Detected",
                "Please add at least one point cloud layer to the Fuel Table before generating.",
            )
            return

        # --- Safe Type Casting ---
        fuel_layers = []
        for row in range(self.ui.table_fuel_layers.rowCount()):
            try:
                layer = {
                    "filename": self.ui.table_fuel_layers.item(row, 0).text(),
                    "semantic_class": self.ui.table_fuel_layers.cellWidget(
                        row, 1
                    ).currentText(),
                    "bulk_density": float(
                        self.ui.table_fuel_layers.item(row, 2).text()
                    ),
                    "moisture_fraction": float(
                        self.ui.table_fuel_layers.item(row, 3).text()
                    ),
                    "sv_ratio": float(self.ui.table_fuel_layers.item(row, 4).text()),
                    "length": float(self.ui.table_fuel_layers.item(row, 5).text()),
                    "drag": float(self.ui.table_fuel_layers.item(row, 6).text()),
                }
                fuel_layers.append(layer)
            except ValueError:
                QMessageBox.critical(
                    self.ui,
                    "Data Error",
                    f"Invalid number format in Table Row {row + 1}. Density and Moisture must be valid numbers.",
                )
                return

        # --- DATA MODELS: Instantiating our Dataclasses ---
        ros_tracking = (
            self.ui.check_ros_tracking.isChecked()
            if hasattr(self.ui, "check_ros_tracking")
            else False
        )
        env_params = EnvParams(
            sim_time=self.ui.spin_sim_time.value(),
            wind_dev_time=self.ui.spin_wind_dev.value(),
            wind_dir=self.ui.spin_wind_dir.value(),
            wind_speed=self.ui.spin_wind_speed.value(),
            hrrpua=self.ui.spin_hrrpua.value(),
            track_embers=self.ui.check_track_embers.isChecked(),
            ign_duration=self.ui.spin_ign_duration.value(),
            obukhov=self.ui.spin_obukhov.value(),
            z0=self.ui.spin_z0.value(),
            ember_density=self.ui.spin_ember_density.value(),
            ember_velocity=self.ui.spin_ember_velocity.value(),
            ign_pattern=self.ui.combo_ign_pattern.currentText(),
            vent_width=self.ui.spin_vent_width.value(),
            ros_tracking=ros_tracking,
        )

        litter_active = (
            self.ui.check_litter.isChecked()
            if hasattr(self.ui, "check_litter")
            else True
        )
        litter_depth = (
            self.ui.spin_litter_depth.value()
            if hasattr(self.ui, "spin_litter_depth")
            else 0.05
        )
        litter_bd = (
            self.ui.spin_litter_bd.value()
            if hasattr(self.ui, "spin_litter_bd")
            else 15.0
        )
        litter_moisture = (
            self.ui.spin_litter_moisture.value()
            if hasattr(self.ui, "spin_litter_moisture")
            else 0.1
        )

        litter_model_mode = (
            self.ui.combo_litter_model.currentText()
            if hasattr(self.ui, "combo_litter_model")
            else "Uniform"
        )
        tree_map_path = (
            self.ui.line_tree_map_path.text().strip()
            if hasattr(self.ui, "line_tree_map_path")
            else ""
        )
        dtm_path = (
            self.ui.line_dtm_path.text().strip()
            if hasattr(self.ui, "line_dtm_path")
            else ""
        )
        decay_alpha = (
            self.ui.spin_decay_alpha.value()
            if hasattr(self.ui, "spin_decay_alpha")
            else 0.5
        )
        min_litter_bd = (
            self.ui.spin_min_litter_bd.value()
            if hasattr(self.ui, "spin_min_litter_bd")
            else 2.0
        )
        turnover_rate = (
            self.ui.spin_turnover_rate.value()
            if hasattr(self.ui, "spin_turnover_rate")
            else 0.20
        )
        accumulation_years = (
            self.ui.spin_accumulation_years.value()
            if hasattr(self.ui, "spin_accumulation_years")
            else 3.0
        )
        dispersion_sigma = (
            self.ui.spin_dispersion_sigma.value()
            if hasattr(self.ui, "spin_dispersion_sigma")
            else 1.5
        )
        num_litter_bins = (
            self.ui.spin_num_litter_bins.value()
            if hasattr(self.ui, "spin_num_litter_bins")
            else 10
        )

        ground_fuels = GroundFuels(
            litter_active=litter_active,
            litter_depth=litter_depth,
            litter_bd=litter_bd,
            litter_moisture=litter_moisture,
            litter_model_mode=litter_model_mode,
            tree_map_path=tree_map_path,
            dtm_path=dtm_path,
            decay_alpha=decay_alpha,
            min_litter_bd=min_litter_bd,
            turnover_rate=turnover_rate,
            accumulation_years=accumulation_years,
            dispersion_sigma=dispersion_sigma,
            num_litter_bins=num_litter_bins,
        )

        restart_active = (
            self.ui.check_restart_active.isChecked()
            if hasattr(self.ui, "check_restart_active")
            else False
        )
        dt_restart = (
            self.ui.spin_dt_restart.value()
            if hasattr(self.ui, "spin_dt_restart")
            else 25.0
        )
        dt_hrr = self.ui.spin_dt_hrr.value() if hasattr(self.ui, "spin_dt_hrr") else 0.1
        dt_devc = (
            self.ui.spin_dt_devc.value() if hasattr(self.ui, "spin_dt_devc") else 0.1
        )
        dt_part = (
            self.ui.spin_dt_part.value() if hasattr(self.ui, "spin_dt_part") else 0.1
        )
        slice_heights = (
            self.ui.line_slice_heights.text().strip()
            if hasattr(self.ui, "line_slice_heights")
            else "1.0"
        )

        output_params = OutputParams(
            hrrpua=self.ui.check_out_hrrpua.isChecked(),
            flame=self.ui.check_out_flame.isChecked(),
            temp=self.ui.check_out_temp.isChecked(),
            wind=self.ui.check_out_wind.isChecked(),
            biomass=self.ui.check_out_biomass.isChecked(),
            restart_active=restart_active,
            dt_restart=dt_restart,
            dt_hrr=dt_hrr,
            dt_devc=dt_devc,
            dt_part=dt_part,
            slice_heights=slice_heights,
        )

        domain_params = DomainParams(
            lateral_pad=self.ui.spin_lateral_pad.value(),
            top_pad=self.ui.spin_top_pad.value(),
            sky_multiplier=sky_mult,
            mpi_x=self.ui.spin_mpi_x.value(),
            mpi_y=self.ui.spin_mpi_y.value(),
        )

        runtime_config = RuntimeConfig(
            input_directory=input_dir,
            output_directory=output_dir,
            output_filename=output_filename,
            preset_name=selected_preset,
            voxel_size=voxel_size,
            fuel_layers=fuel_layers,
            env_params=env_params,
            ground_fuels=ground_fuels,
            output_params=output_params,
            domain_params=domain_params,
        )

        # 3. Disable UI and Start Background Thread
        self.ui.btn_generate.setEnabled(False)
        if hasattr(self.ui, "progress_bar"):
            self.ui.progress_bar.setValue(0)  # Reset to 0 when starting

        self.log("--- Starting TLS to FDS Pipeline ---")

        # Instantiate the worker, connect its signals, and start it
        self.worker = PipelineWorker(runtime_config)
        self.worker.log_signal.connect(self.log)

        # Connect the progress signal to the progress bar
        if hasattr(self.ui, "progress_bar"):
            self.worker.progress_signal.connect(self.ui.progress_bar.setValue)

        self.worker.finished_signal.connect(self.on_pipeline_finished)
        self.worker.start()

    def on_pipeline_finished(self):
        """Re-enables the generate button once the background thread completes."""
        self.ui.btn_generate.setEnabled(True)
        self.log("--- Thread Execution Finished ---")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window_controller = TLS_to_FDS_GUI()
    window_controller.ui.show()
    sys.exit(app.exec())
