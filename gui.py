import sys
import traceback
import utils
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QTableWidgetItem, QHeaderView, QComboBox
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import QFile, QThread, Signal

# Import pipeline execution engine
from main import run_pipeline

class PipelineWorker(QThread):
    """
    Background thread to execute the FDS voxelization pipeline.
    Prevents the main GUI from freezing during heavy 3D processing.
    """
    log_signal = Signal(str)
    finished_signal = Signal()

    def __init__(self, runtime_config):
        super().__init__()
        self.config = runtime_config

    def run(self):
        # We pass a lambda function so the pipeline's print statements 
        # emit our Qt Signal instead of printing to the hidden system console.
        try:
            run_pipeline(self.config, log_callback=lambda msg: self.log_signal.emit(str(msg)))
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
        self.ui.resize(1000, 700)
        
        # 2. Wire Up Directory Selection Signals
        self.ui.btn_browse_input.clicked.connect(self.browse_input_dir)
        self.ui.btn_browse_output.clicked.connect(self.browse_output_dir)
        
        # 3. Wire Up Table Manipulation Signals
        self.ui.btn_add_layer.clicked.connect(self.add_layer_row)
        self.ui.btn_remove_layer.clicked.connect(self.remove_layer_row)

        # Configure Table Columns
        self.ui.table_fuel_layers.setColumnCount(3)
        self.ui.table_fuel_layers.setHorizontalHeaderLabels(["Filename", "Semantic Class", "Bulk Density (kg/m³)"])
        
        header = self.ui.table_fuel_layers.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)   # Filename takes up all extra space
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)   # Dropdown fits its text perfectly
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)   # Density fits its text perfectly

        # 4. Wire Up Execution Pipeline
        self.ui.btn_generate.clicked.connect(self.generate_fds)

        # Initialize dynamic preset data
        self.populate_presets()

        # Auto-update densities if the global preset is changed ---
        self.ui.combo_preset.currentTextChanged.connect(self.refresh_all_densities)

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
    
    def update_bulk_density(self, row, combo_box):
        """Reads the JSON preset and updates the density cell for a specific row."""
        preset_name = self.ui.combo_preset.currentText()
        if preset_name and preset_name != "No forest presets found":
            try:
                preset_data = utils.load_preset(preset_name)
                semantic_class = combo_box.currentText()
                if semantic_class in preset_data:
                    bd = preset_data[semantic_class].get("default_bulk_density", 0.8)
                    self.ui.table_fuel_layers.item(row, 2).setText(str(bd))
            except Exception as e:
                self.log(f"Warning: Could not read density: {str(e)}")

    def refresh_all_densities(self):
        """Updates all rows if the user changes the global Forest Preset dropdown."""
        for row in range(self.ui.table_fuel_layers.rowCount()):
            combo = self.ui.table_fuel_layers.cellWidget(row, 1)
            if combo:
                self.update_bulk_density(row, combo)

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
            
            # Populate Column 2: Insert a dummy item FIRST so the combo box has an item to overwrite
            self.ui.table_fuel_layers.setItem(row_count, 2, QTableWidgetItem("0.0")) 
            
            # Wire the dropdown to update the density cell on change
            combo_class.currentTextChanged.connect(
                lambda text, r=row_count, cb=combo_class: self.update_bulk_density(r, cb)
            )
            
            self.ui.table_fuel_layers.setCellWidget(row_count, 1, combo_class) 
            
            # Trigger it once manually to apply the current preset's starting value
            self.update_bulk_density(row_count, combo_class)
            
            self.log(f"Added layer reference: {file_name}")

    def remove_layer_row(self):
        current_row = self.ui.table_fuel_layers.currentRow()
        if current_row >= 0:
            self.ui.table_fuel_layers.removeRow(current_row)
            self.log(f"Removed layer config index row: {current_row}")

    def generate_fds(self):
        # 1. Scrape data structures out of UI input nodes
        input_dir = self.ui.line_input_dir.text()
        output_dir = self.ui.line_output_dir.text()
        voxel_size = self.ui.spin_voxel_size.value()
        selected_preset = self.ui.combo_preset.currentText()
        
        if not input_dir or not output_dir:
            self.log("Error: Target and Source directories must be explicitly set before compiling.")
            return
            
        # Extract Environment Parameters
        env_params = {
            "sim_time": self.ui.spin_sim_time.value(),
            "wind_dev_time": self.ui.spin_wind_dev.value(),
            "wind_dir": self.ui.spin_wind_dir.value(),
            "wind_speed": self.ui.spin_wind_speed.value(),
            "hrrpua": self.ui.spin_hrrpua.value()
        }
            
        # 2. Extract fuel array rows from dynamic table
        fuel_layers = []
        for row in range(self.ui.table_fuel_layers.rowCount()):
            try:
                filename = self.ui.table_fuel_layers.item(row, 0).text()
                semantic_class = self.ui.table_fuel_layers.cellWidget(row, 1).currentText()
                bd_value = float(self.ui.table_fuel_layers.item(row, 2).text())
                
                fuel_layers.append({
                    "filename": filename,
                    "semantic_class": semantic_class,
                    "bulk_density": bd_value
                })
            except (AttributeError, ValueError):
                self.log(f"Skipping malformed row configuration structural data entry at index: {row}")

        # Assemble runtime configuration model
        runtime_config = {
            "input_directory": input_dir,
            "output_directory": output_dir,
            "voxel_size": voxel_size,
            "preset_name": selected_preset,
            "fuel_layers": fuel_layers,
            "env_params": env_params
        }

        # 3. Disable UI and Start Background Thread
        self.ui.btn_generate.setEnabled(False)
        self.log("--- Starting TLS to FDS Pipeline ---")
        
        # Instantiate the worker, connect its signals, and start it
        self.worker = PipelineWorker(runtime_config)
        self.worker.log_signal.connect(self.log)
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