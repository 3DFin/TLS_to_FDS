import sys
import traceback
import utils
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QStyle, QTableWidgetItem, QHeaderView, QComboBox, QMessageBox
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, QThread, Signal
import qdarktheme

from main import run_pipeline
from models import EnvParams, GroundFuels, OutputParams, RuntimeConfig
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
        self.ui.resize(1000, 860)
        
        # Aesthetic: Set standard icons for buttons
        style = self.ui.style()
        self.ui.btn_browse_input.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self.ui.btn_browse_output.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        self.ui.btn_add_layer.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.ui.btn_remove_layer.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.ui.btn_generate.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        
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
        self.ui.table_fuel_layers.setColumnCount(4)
        self.ui.table_fuel_layers.setHorizontalHeaderLabels(["Filename", "Fuel Class", "Bulk Density (kg/m³)", "Moisture Fraction"])
        
        header = self.ui.table_fuel_layers.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)   # Filename
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)   # Dropdown Fuel Class
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)   # Bulk Density
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)   # Moisture Fraction

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
                    bd = preset_data[semantic_class].get("default_bulk_density", 0.8)
                    mf = preset_data[semantic_class].get("moisture_fraction", 0.15)
                    self.ui.table_fuel_layers.item(row, 2).setText(str(bd))
                    self.ui.table_fuel_layers.item(row, 3).setText(str(mf)) # Update Moisture
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
            
            # Populate Column 2 & 3: Insert a dummy item FIRST so the combo box has an item to overwrite
            self.ui.table_fuel_layers.setItem(row_count, 2, QTableWidgetItem("0.0"))
            self.ui.table_fuel_layers.setItem(row_count, 3, QTableWidgetItem("0.0"))
            
            # Wire the dropdown to update the density cell on change
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

    def generate_fds(self):
        # 1. Scrape data structures out of UI input nodes
        input_dir = self.ui.line_input_dir.text().strip()
        output_dir = self.ui.line_output_dir.text().strip()
        voxel_size = self.ui.spin_voxel_size.value()
        selected_preset = self.ui.combo_preset.currentText()
        output_filename = self.ui.line_output_name.text().strip() or "model"

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
                    "moisture_fraction": float(self.ui.table_fuel_layers.item(row, 3).text())
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

        runtime_config = RuntimeConfig(
            input_directory=input_dir,
            output_directory=output_dir,
            output_filename=output_filename,
            preset_name=selected_preset,
            voxel_size=voxel_size,
            fuel_layers=fuel_layers,
            env_params=env_params,
            ground_fuels=ground_fuels,
            output_params=output_params
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