import json
import sys
import traceback
import utils
import laspy
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QStyle, QTableWidgetItem, QHeaderView, QComboBox, QMessageBox, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTextBrowser
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, QThread, Signal, QUrl
from PySide6.QtGui import QFont, QPixmap
import qdarktheme

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineSettings
    WEB_ENGINE_AVAILABLE = True
except ImportError:
    WEB_ENGINE_AVAILABLE = False

from main import run_pipeline
from models import EnvParams, GroundFuels, OutputParams, DomainParams, RuntimeConfig
from constants import WELCOME_BANNER, TOOLTIPS

class PipelineWorker(QThread):
    """
    Background thread to execute the FDS voxelization pipeline.
    Prevents the main GUI from freezing during heavy 3D processing.
    """
    log_signal = Signal(str)
    progress_signal = Signal(int)
    finished_signal = Signal()

    def __init__(self, runtime_config):
        super().__init__()
        self.config = runtime_config

    def run(self):
        # We pass a lambda function so the pipeline's print statements 
        # emit our Qt Signal instead of printing to the hidden system console.
        try:
            run_pipeline(
                self.config, 
                log_callback=lambda msg: self.log_signal.emit(str(msg)),
                progress_callback=lambda val: self.progress_signal.emit(int(val))
            )
        except Exception as e:
            # Print the full error stack trace so we know exactly why it froze
            err_msg = traceback.format_exc()
            self.log_signal.emit(f"FATAL ERROR: Pipeline crashed:\n{err_msg}")
        finally:
            self.finished_signal.emit()

class DomainWizardDialog(QDialog):
    def __init__(self, parent, forest_width, current_pad, current_voxel, current_mult, current_mpi):
        super().__init__(parent)
        self.setWindowTitle("Interactive FDS Domain Alignment Wizard")
        self.resize(1100, 800)
        
        layout = QVBoxLayout(self)
        
        self.browser = QWebEngineView()
        self.browser.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        # Use .resolve() to guarantee a perfect absolute path on Windows
        html_path = (Path(__file__).parent / "mesh_visualizer.html").resolve()

        # Safety Check: Warn the user if the HTML file isn't found instead of a Chromium error
        if not html_path.exists():
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(parent, "Missing File", 
                                 f"Could not find the 3D visualizer HTML file at:\n{html_path}\n\n"
                                 "Please ensure 'mesh_visualizer.html' is saved in the same directory as gui.py.")
            self.browser.setHtml("<h2 style='color:red; font-family:sans-serif; text-align:center; padding:50px;'>Error: mesh_visualizer.html not found.</h2>")
        else:
            self.browser.setUrl(QUrl.fromLocalFile(str(html_path)))

        layout.addWidget(self.browser)
        
        btn_layout = QHBoxLayout()
        self.btn_apply = QPushButton("Apply Settings & Close")
        self.btn_apply.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; padding: 10px; border-radius: 5px;")
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet("padding: 10px;")
        
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_apply)
        layout.addLayout(btn_layout)
        
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_apply.clicked.connect(self.apply_settings)
        
        self.results = {}
        # Wait for HTML to load before injecting JavaScript
        self.browser.loadFinished.connect(lambda: self.inject_initial_values(forest_width, current_pad, current_voxel, current_mult, current_mpi))

    def inject_initial_values(self, w, pad, vox, mult, mpi):
        js = f"""
        function injectWhenReady() {{
            if (typeof updateVisualization === 'function' && typeof THREE !== 'undefined') {{
                document.getElementById('slider-forest').value = {w};
                document.getElementById('slider-forest').disabled = true; // Lock forest size!
                document.getElementById('slider-pad').value = {pad};
                document.getElementById('slider-voxel').value = {vox};
                document.getElementById('slider-mult').value = {mult};
                document.getElementById('slider-mpi').value = {mpi};
                updateVisualization();
            }} else {{
                setTimeout(injectWhenReady, 50); // Check again in 50ms
            }}
        }}
        injectWhenReady();
        """
        self.browser.page().runJavaScript(js)

    def apply_settings(self):
        js = """
        JSON.stringify({
            pad: document.getElementById('slider-pad').value,
            vox: document.getElementById('slider-voxel').value,
            mult: document.getElementById('slider-mult').value,
            mpi: document.getElementById('slider-mpi').value
        })
        """
        self.browser.page().runJavaScript(js, self.on_js_result)
        
    def on_js_result(self, result_str):
        self.results = json.loads(result_str)
        self.accept()

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
        self.ui.setWindowTitle("TLS_to_FDS - FDS inputs from Ground-Based Forest Point Clouds")
        self.ui.resize(1000, 880)

        # Inject the About Tab content dynamically
        self.setup_about_tab()
        
        # Aesthetic: Set standard icons for buttons
        style = self.ui.style()
        self.ui.btn_browse_input.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        self.ui.btn_browse_output.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        self.ui.btn_add_layer.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.ui.btn_remove_layer.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.ui.btn_generate.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))

        # Aesthetic: Make the Generate Button pop
        self.ui.btn_generate.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32; /* Deep modern green */
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 5px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #388e3c; /* Lighter green on hover */
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #777777;
            }
        """)

        # Aesthetic: Style the progress bar to match the Generate Button
        if hasattr(self.ui, 'progress_bar'):
            self.ui.progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #444;
                    border-radius: 4px;
                    text-align: center;
                    color: white;
                    font-weight: bold;
                }
                QProgressBar::chunk {
                    background-color: #2e7d32;
                    border-radius: 3px;
                }
            """)

        # Aesthetic: Make the console look like a true terminal
        console_font = QFont("Consolas", 10) # Monospace font
        self.ui.text_console.setFont(console_font)
        # Give it a slightly darker background than the rest of the app
        self.ui.text_console.setStyleSheet("background-color: #0d0d0d; border: 1px solid #333;")
        
        # Aesthetic: insert forest schematic into the GUI
        image_path = Path(__file__).parent / "fig_fuel_layers_lbls.png"
        if image_path.exists():
            pixmap = QPixmap(str(image_path))
            self.ui.lbl_forest_schematic.setPixmap(pixmap)
        else:
            self.log("Warning: fig_fuel_layers_lbls.png not found in the root directory.")

        # Reset progress bar just in case
        if hasattr(self.ui, 'progress_bar'):
            self.ui.progress_bar.setValue(0)

        # 2. Wire Up Directory Selection Signals
        self.ui.btn_browse_input.clicked.connect(self.browse_input_dir)
        self.ui.btn_browse_output.clicked.connect(self.browse_output_dir)

        # --- Wire Up Dynamic Ground Fuel Toggling
        self.ui.check_litter.toggled.connect(self.ui.spin_litter_depth.setEnabled)
        self.ui.check_litter.toggled.connect(self.ui.spin_litter_bd.setEnabled)
        self.ui.check_litter.toggled.connect(self.ui.spin_litter_moisture.setEnabled)
        
        self.ui.check_duff.toggled.connect(self.ui.spin_duff_depth.setEnabled)
        self.ui.check_duff.toggled.connect(self.ui.spin_duff_bd.setEnabled)
        self.ui.check_duff.toggled.connect(self.ui.spin_duff_moisture.setEnabled)
        
        # 3. Wire Up Table Manipulation Signals
        self.ui.btn_add_layer.clicked.connect(self.add_layer_row)
        self.ui.btn_remove_layer.clicked.connect(self.remove_layer_row)

        # Configure Table Columns
        self.ui.table_fuel_layers.setColumnCount(7)
        self.ui.table_fuel_layers.setHorizontalHeaderLabels([
            "Filename", "Fuel Class", "Bulk Density", "Moisture", 
            "S/V Ratio", "Length (m)", "Drag",
        ])

        header = self.ui.table_fuel_layers.horizontalHeader()
        for i in range(0, 7):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        # 4. Apply External Tooltips
        for widget_name, tooltip_text in TOOLTIPS.items():
            widget = getattr(self.ui, widget_name, None)
            if widget:
                widget.setToolTip(tooltip_text)

        # 5. Connect the checkbox signal directly to the spin boxes' enabled state
        self.ui.check_track_embers.toggled.connect(self.ui.spin_ember_density.setEnabled)
        self.ui.check_track_embers.toggled.connect(self.ui.spin_ember_velocity.setEnabled)
        
        # 6. Trigger it once manually so they start in the correct state when the app launches
        initial_state = self.ui.check_track_embers.isChecked()
        self.ui.spin_ember_density.setEnabled(initial_state)
        self.ui.spin_ember_velocity.setEnabled(initial_state)

        # 7. Wire Up Execution Pipeline
        self.ui.btn_generate.clicked.connect(self.generate_fds)

        #  And wire up the 3D Wizard
        if hasattr(self.ui, 'btn_wizard'):
            self.ui.btn_wizard.clicked.connect(self.launch_wizard)

        # 8. Print the Welcome Banner
        self.log(WELCOME_BANNER)

        # 9. Initialize dynamic preset data
        self.populate_presets()

        # Auto-update densities if the global preset is changed ---
        self.ui.combo_preset.currentTextChanged.connect(self.update_preset_tooltip_and_rows)

    def log(self, message):
        """ Appends status updates safely into the embedded GUI text terminal. """
        self.ui.text_console.append(str(message))
        # Autoscroll to the bottom
        self.ui.text_console.ensureCursorVisible()
    
    def calculate_global_forest_width(self):
        """Instantly reads LAS headers without loading points to find the global footprint."""
        input_dir = Path(self.ui.line_input_dir.text().strip())
        if not input_dir.exists():
            return None
            
        global_min_x, global_min_y = float('inf'), float('inf')
        global_max_x, global_max_y = float('-inf'), float('-inf')
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
                    self.log(f"<span style='color: #ef5350;'>Warning: Could not read header of {filename} - {e}</span>")
                    
        if valid_files == 0:
            return None
            
        width_x = global_max_x - global_min_x
        width_y = global_max_y - global_min_y
        return max(width_x, width_y) # Visualizer MVP uses largest dimension
        
    def launch_wizard(self):
        if not WEB_ENGINE_AVAILABLE:
            QMessageBox.critical(self.ui, "Missing Dependency", "Please run 'pip install PySide6-WebEngine' to use the 3D visualizer.")
            return
            
        if self.ui.table_fuel_layers.rowCount() == 0:
            QMessageBox.warning(self.ui, "No Fuels", "Please add at least one fuel layer to calculate forest bounds.")
            return
            
        forest_width = self.calculate_global_forest_width()
        if forest_width is None:
            QMessageBox.warning(self.ui, "File Error", "Could not read point cloud boundaries from the input directory.")
            return
            
        # Scrape current UI values
        pad = self.ui.spin_lateral_pad.value()
        vox = self.ui.spin_voxel_size.value()
        
        sky_text = self.ui.combo_sky_mult.currentText().replace("x", "")
        mult = int(sky_text) if sky_text else 2
        mpi = self.ui.spin_mpi_x.value()
        
        # Launch Dialog
        dialog = DomainWizardDialog(self.ui, forest_width, pad, vox, mult, mpi)
        if dialog.exec() == QDialog.Accepted:
            res = dialog.results
            self.ui.spin_lateral_pad.setValue(float(res['pad']))
            self.ui.spin_voxel_size.setValue(float(res['vox']))
            self.ui.spin_mpi_x.setValue(int(res['mpi']))
            
            idx = self.ui.combo_sky_mult.findText(f"{res['mult']}x")
            if idx >= 0:
                self.ui.combo_sky_mult.setCurrentIndex(idx)
                
            self.log("<span style='color: #4caf50;'><b>SUCCESS:</b> Applied perfectly aligned domain settings from the 3D Wizard!</span>")

    def browse_input_dir(self):
        directory = QFileDialog.getExistingDirectory(self.ui, "Select Input Point Clouds Directory")
        if directory:
            self.ui.line_input_dir.setText(directory)
            self.log(f"Input source changed to: {directory}")

    def browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self.ui, "Select FDS Output Target Directory")
        if directory:
            self.ui.line_output_dir.setText(directory)
            self.log(f"Output targets changed to: {directory}")

    def populate_presets(self):
        """Scans the presets directory and populates the dropdown menu."""
        preset_dir = Path("presets")
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
                preset_data = utils.load_preset(preset_name)
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
                preset_data = utils.load_preset(preset_name)
                
                if "Litter" in preset_data:
                    self.ui.spin_litter_bd.setValue(preset_data["Litter"].get("default_bulk_density", 15.0))
                    self.ui.spin_litter_moisture.setValue(preset_data["Litter"].get("moisture_fraction", 0.05))
                    
                if "Duff" in preset_data:
                    self.ui.spin_duff_bd.setValue(preset_data["Duff"].get("default_bulk_density", 50.0))
                    self.ui.spin_duff_moisture.setValue(preset_data["Duff"].get("moisture_fraction", 0.10))
                    
            except Exception as e:
                self.log(f"Warning: Could not read synthetic fuel properties: {str(e)}")

    def update_row_parameters(self, row, combo_box):
        """Reads the JSON preset and updates BOTH density and moisture cells."""
        preset_name = self.ui.combo_preset.currentText()
        if preset_name and preset_name != "No forest presets found":
            try:
                preset_data = utils.load_preset(preset_name)
                semantic_class = combo_box.currentText()
                if semantic_class in preset_data:
                    
                    props = preset_data[semantic_class]
                    self.ui.table_fuel_layers.item(row, 2).setText(str(props.get("default_bulk_density", 0.8)))
                    self.ui.table_fuel_layers.item(row, 3).setText(str(props.get("moisture_fraction", 0.15)))
                    self.ui.table_fuel_layers.item(row, 4).setText(str(props.get("sv_ratio", 3588.0)))
                    self.ui.table_fuel_layers.item(row, 5).setText(str(props.get("length", 0.10)))
                    self.ui.table_fuel_layers.item(row, 6).setText(str(props.get("drag", 2.8)))
            except Exception as e:
                self.log(f"Warning: Could not read preset parameters: {str(e)}")

    def add_layer_row(self):
        # Open file browser restricted to point cloud types
        files, _ = QFileDialog.getOpenFileNames(
            self.ui, "Select Forest Fuel Layer Files", 
            self.ui.line_input_dir.text(), "Point Clouds (*.las *.laz *.txt)"
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
                continue # Skip to the next file if this one is a duplicate
            # --------------------------------------------------------
            
            row_count = self.ui.table_fuel_layers.rowCount()
            self.ui.table_fuel_layers.insertRow(row_count)
            
            # Populate Column 0: Filename
            self.ui.table_fuel_layers.setItem(row_count, 0, QTableWidgetItem(file_name))
            
            # Populate Column 1: Dynamic Dropdown for Semantic Class
            combo_class = QComboBox()
            combo_class.addItems([ "Ground Fuel", "Surface Fuel", "Ladder Fuel", "Trunks",])
            
            # Populate Columns 2 to 6: Insert blank dummy items FIRST
            for col in range(2, 7):
                self.ui.table_fuel_layers.setItem(row_count, col, QTableWidgetItem(""))
            
            combo_class.currentTextChanged.connect(
                lambda text, r=row_count, cb=combo_class: self.update_row_parameters(r, cb)
            )
            
            self.ui.table_fuel_layers.setCellWidget(row_count, 1, combo_class) 
            
            # Trigger it once manually to apply the current preset's starting value
            self.update_row_parameters(row_count, combo_class)
            
            self.log(f"Added layer reference: {file_name}")

    def remove_layer_row(self):
        current_row = self.ui.table_fuel_layers.currentRow()
        if current_row >= 0:
            self.ui.table_fuel_layers.removeRow(current_row)
            self.log(f"Removed layer config index row: {current_row}")

    def setup_about_tab(self):
        """Dynamically creates and appends an About/References tab to the GUI."""
        self.tab_about = QWidget()
        layout = QVBoxLayout()
        
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True) # Make HTML links clickable
        
        html_content = """
        <div style="font-family: 'Segoe UI', Arial, sans-serif; padding: 20px;">
            <h1 style="color: #2e7d32; margin-bottom: 0px;">TLS_to_FDS</h1>
            <p style="font-size: 14px; margin-top: 0px;"><b>Version 1.0</b> | Point Cloud to Fire Simulation Pipeline</p>
            <hr>
            
            <h3>📖 Overview</h3>
            <p>TLS_to_FDS is an open-source framework designed to automate the conversion of semantically segmented ground-based point clouds (like Terrestrial Laser Scanning) into ready-to-run input files for the Fire Dynamics Simulator (FDS).</p>
            
            <h3>🔬 Scientific References & Sub-Models</h3>
            <ul>
                <li style="margin-bottom: 10px;"><b>Fire Dynamics Simulator (FDS):</b> McGrattan, K., Hostikka, S., McDermott, R., Floyd, J., Weinschenk, C., & Overholt, K. (2023). <i>Fire Dynamics Simulator User's Guide</i>. NIST Special Publication 1019.</li>
                <li style="margin-bottom: 10px;"><b>Synthetic Ground Fuels:</b> Implemented utilizing the FDS 1D Boundary Fuel Model to simulate sub-grid litter and duff heat transfer without computationally exhaustive particle tracking.</li>
                <li style="margin-bottom: 10px;"><b>Atmospheric Physics:</b> Stratification and wind profile models are parameterized via the Monin-Obukhov similarity theory (Obukhov Length).</li>
                <li style="margin-bottom: 10px;"><b>Firebrand Tracking:</b> Enabled via Lagrangian particles using user-defined density and velocity lofting thresholds.</li>
            </ul>
            
            <hr>
            <p style="color: gray; font-size: 12px;"><i>This software utilizes <b>laspy</b> for geospatial parsing, <b>dendroptimized</b> for spatial voxelization, and <b>PySide6</b> for the graphical user interface.</i></p>
        </div>
        """
        browser.setHtml(html_content)
        layout.addWidget(browser)
        self.tab_about.setLayout(layout)
        
        # Add it to the existing QTabWidget found in the UI
        self.ui.tabs.addTab(self.tab_about, "About / References")

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
            sky_mult = 2 # Fallback safety

        # --- Pre-Flight Checks ---
        if not input_dir or not Path(input_dir).exists():
            QMessageBox.critical(self.ui, "Directory Error", "Please provide a valid Input Directory.")
            return
            
        if not output_dir or not Path(output_dir).exists():
            QMessageBox.critical(self.ui, "Directory Error", "Please provide a valid Output Directory.")
            return

        if self.ui.table_fuel_layers.rowCount() == 0:
            QMessageBox.warning(self.ui, "No Fuels Detected", "Please add at least one point cloud layer to the Fuel Table before generating.")
            return

        # --- Safe Type Casting ---
        fuel_layers = []
        for row in range(self.ui.table_fuel_layers.rowCount()):
            try:
                layer = {
                    "filename": self.ui.table_fuel_layers.item(row, 0).text(),
                    "semantic_class": self.ui.table_fuel_layers.cellWidget(row, 1).currentText(),
                    "bulk_density": float(self.ui.table_fuel_layers.item(row, 2).text()),
                    "moisture_fraction": float(self.ui.table_fuel_layers.item(row, 3).text()),
                    "sv_ratio": float(self.ui.table_fuel_layers.item(row, 4).text()),
                    "length": float(self.ui.table_fuel_layers.item(row, 5).text()),
                    "drag": float(self.ui.table_fuel_layers.item(row, 6).text()),
                }
                fuel_layers.append(layer)
            except ValueError:
                QMessageBox.critical(self.ui, "Data Error", f"Invalid number format in Table Row {row+1}. Density and Moisture must be valid numbers.")
                return 

        # --- DATA MODELS: Instantiating our Dataclasses ---
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
            vent_width=self.ui.spin_vent_width.value()
        )

        ground_fuels = GroundFuels(
            litter_active=self.ui.check_litter.isChecked(),
            litter_depth=self.ui.spin_litter_depth.value(),
            litter_bd=self.ui.spin_litter_bd.value(),
            litter_moisture=self.ui.spin_litter_moisture.value(),
            duff_active=self.ui.check_duff.isChecked(),
            duff_depth=self.ui.spin_duff_depth.value(),
            duff_bd=self.ui.spin_duff_bd.value(),
            duff_moisture=self.ui.spin_duff_moisture.value()
        )

        output_params = OutputParams(
            hrrpua=self.ui.check_out_hrrpua.isChecked(),
            flame=self.ui.check_out_flame.isChecked(),
            temp=self.ui.check_out_temp.isChecked(),
            wind=self.ui.check_out_wind.isChecked(),
            biomass=self.ui.check_out_biomass.isChecked()
        )

        domain_params = DomainParams(
            lateral_pad=self.ui.spin_lateral_pad.value(),
            top_pad=self.ui.spin_top_pad.value(),
            sky_multiplier=sky_mult,
            mpi_x=self.ui.spin_mpi_x.value(),
            mpi_y=self.ui.spin_mpi_y.value()
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
        if hasattr(self.ui, 'progress_bar'):
            self.ui.progress_bar.setValue(0) # Reset to 0 when starting

        self.log("--- Starting TLS to FDS Pipeline ---")

        # Instantiate the worker, connect its signals, and start it
        self.worker = PipelineWorker(runtime_config)
        self.worker.log_signal.connect(self.log)

        # Connect the progress signal to the progress bar
        if hasattr(self.ui, 'progress_bar'):
            self.worker.progress_signal.connect(self.ui.progress_bar.setValue)

        self.worker.finished_signal.connect(self.on_pipeline_finished)
        self.worker.start()

    def on_pipeline_finished(self):
        """Re-enables the generate button once the background thread completes."""
        self.ui.btn_generate.setEnabled(True)
        self.log("--- Thread Execution Finished ---")

if __name__ == "__main__":
    qdarktheme.enable_hi_dpi()
    app = QApplication(sys.argv)
    # Apply dark theme to the entire application
    qdarktheme.setup_theme()
    window_controller = TLS_to_FDS_GUI()
    window_controller.ui.show()
    sys.exit(app.exec())