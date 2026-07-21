import subprocess
import sys
import os
from pathlib import Path

def build():
    print("Installing PyInstaller...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    print("Building executable with PyInstaller...")
    command = [
        sys.executable, "-m", "PyInstaller",
        "--name", "TLS_to_FDS",
        "--onedir",
        "--noconsole",
        "--paths", "src",
        "--add-data", f"src/tls_to_fds/mainwindow.ui{os.pathsep}tls_to_fds",
        "--add-data", f"src/tls_to_fds/style.qss{os.pathsep}tls_to_fds",
        "--add-data", f"src/tls_to_fds/fig_fuel_layers_lbls.png{os.pathsep}tls_to_fds",
        "--add-data", f"src/tls_to_fds/default_config.json{os.pathsep}tls_to_fds",
        "--add-data", f"src/tls_to_fds/mesh_visualizer.html{os.pathsep}tls_to_fds",
        "--add-data", f"src/tls_to_fds/js{os.pathsep}tls_to_fds/js",
        "--add-data", f"presets{os.pathsep}presets",
        "run_tls_to_fds.py"
    ]
    
    subprocess.check_call(command)
    print("Build complete! Check the 'dist/TLS_to_FDS' directory.")

if __name__ == "__main__":
    build()
