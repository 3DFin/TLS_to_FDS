import os
import subprocess
import sys
from pathlib import Path


def build():
    print("Installing PyInstaller...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    print("Building executable with PyInstaller...")
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "TLS_to_FDS",
        "--noconfirm",
        "--onedir",
        "--noconsole",
        "--paths",
        "src",
        "--add-data",
        f"src/tls_to_fds/mainwindow.ui{os.pathsep}tls_to_fds",
        "--add-data",
        f"src/tls_to_fds/style.qss{os.pathsep}tls_to_fds",
        "--add-data",
        f"src/tls_to_fds/fig_fuel_layers_lbls.png{os.pathsep}tls_to_fds",
        "--add-data",
        f"src/tls_to_fds/default_config.json{os.pathsep}tls_to_fds",
        "--add-data",
        f"src/tls_to_fds/mesh_visualizer.html{os.pathsep}tls_to_fds",
        "--add-data",
        f"src/tls_to_fds/js{os.pathsep}tls_to_fds/js",
        "--add-data",
        f"presets{os.pathsep}presets",
        "run_tls_to_fds.py",
    ]

    subprocess.check_call(command)

    # Ensure presets folder is also copied directly next to the executable in dist/TLS_to_FDS/presets
    dist_presets = Path("dist/TLS_to_FDS/presets")
    if Path("presets").exists():
        dist_presets.parent.mkdir(parents=True, exist_ok=True)
        import shutil

        shutil.copytree("presets", dist_presets, dirs_exist_ok=True)
        print("Copied presets directory to dist/TLS_to_FDS/presets")

    print("Build complete! Check the 'dist/TLS_to_FDS' directory.")


if __name__ == "__main__":
    build()

