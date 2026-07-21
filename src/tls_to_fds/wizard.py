import json
from pathlib import Path
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox
from PySide6.QtCore import QUrl

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWebEngineCore import QWebEngineSettings
    WEB_ENGINE_AVAILABLE = True
except ImportError:
    WEB_ENGINE_AVAILABLE = False

class DomainWizardDialog(QDialog):
    def __init__(self, parent, forest_width, current_pad, current_top_pad, current_voxel, current_mult, current_mpi_x, current_mpi_y):
        super().__init__(parent)
        self.setWindowTitle("Interactive FDS Domain Alignment Wizard")
        self.resize(1100, 810)
        
        layout = QVBoxLayout(self)
        
        self.browser = QWebEngineView()
        self.browser.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        # Use .resolve() to guarantee a perfect absolute path on Windows
        html_path = (Path(__file__).parent / "mesh_visualizer.html").resolve()

        # Safety Check: Warn the user if the HTML file isn't found instead of a Chromium error
        if not html_path.exists():
            QMessageBox.critical(parent, "Missing File", 
                                 f"Could not find the 3D visualizer HTML file at:\\n{html_path}\\n\\n"
                                 "Please ensure 'mesh_visualizer.html' is saved in the same directory as wizard.py.")
            self.browser.setHtml("<h2 style='color:red; font-family:sans-serif; text-align:center; padding:50px;'>Error: mesh_visualizer.html not found.</h2>")
        else:
            self.browser.setUrl(QUrl.fromLocalFile(str(html_path)))

        layout.addWidget(self.browser)
        
        btn_layout = QHBoxLayout()
        self.btn_apply = QPushButton("Apply Settings and Close")
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
        self.browser.loadFinished.connect(lambda: self.inject_initial_values(forest_width, current_pad, current_top_pad, current_voxel, current_mult, current_mpi_x, current_mpi_y))

    def inject_initial_values(self, w, pad, top_pad, vox, mult, mpi_x, mpi_y):
        js = f"""
        function injectWhenReady() {{
            if (typeof updateVisualization === 'function' && typeof THREE !== 'undefined') {{
                document.getElementById('slider-forest').value = {w};
                document.getElementById('slider-forest').disabled = true; // Lock forest size!
                document.getElementById('slider-pad').value = {pad};
                document.getElementById('slider-top-pad').value = {top_pad};
                document.getElementById('slider-voxel').value = {vox};
                document.getElementById('slider-mult').value = {mult};
                document.getElementById('slider-mpi-x').value = {mpi_x};
                document.getElementById('slider-mpi-y').value = {mpi_y};
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
            top_pad: document.getElementById('slider-top-pad').value,
            vox: document.getElementById('slider-voxel').value,
            mult: document.getElementById('slider-mult').value,
            mpi_x: document.getElementById('slider-mpi-x').value,
            mpi_y: document.getElementById('slider-mpi-y').value
        })
        """
        self.browser.page().runJavaScript(js, self.on_js_result)
        
    def on_js_result(self, result_str):
        self.results = json.loads(result_str)
        self.accept()
