import os
import shutil
import subprocess
import sys
from pathlib import Path


def build():
    is_macos = sys.platform == "darwin"

    print("Checking / Installing PyInstaller...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    print(f"Building standalone application with PyInstaller on {sys.platform}...")
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "TLS_to_FDS",
        "--noconfirm",
        "--onedir",
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
    ]

    if is_macos:
        command.extend([
            "--windowed",
            "--osx-bundle-identifier",
            "org.threedfin.tlstofds",
        ])
    else:
        command.append("--noconsole")

    command.append("run_tls_to_fds.py")

    subprocess.check_call(command)

    # --- Copy Presets to Distribution Directories ---
    presets_src = Path("presets")

    # 1. macOS .app bundle paths
    app_path = Path("dist/TLS_to_FDS.app")
    if is_macos and app_path.exists():
        resources_presets = app_path / "Contents" / "Resources" / "presets"
        macos_presets = app_path / "Contents" / "MacOS" / "presets"
        if presets_src.exists():
            resources_presets.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(presets_src, resources_presets, dirs_exist_ok=True)
            print(f"Copied presets to {resources_presets}")

            macos_presets.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(presets_src, macos_presets, dirs_exist_ok=True)
            print(f"Copied presets to {macos_presets}")

        # Ensure executable bit is set on macOS Mach-O binary
        macos_bin = app_path / "Contents" / "MacOS" / "TLS_to_FDS"
        if macos_bin.exists():
            os.chmod(macos_bin, 0o755)

        # Package macOS .zip using ditto (preserves symlinks and resource forks)
        zip_path = Path("dist/TLS_to_FDS_macOS.zip")
        if zip_path.exists():
            zip_path.unlink()
        try:
            subprocess.run(
                [
                    "ditto",
                    "-c",
                    "-k",
                    "--sequesterRsrc",
                    "--keepParent",
                    str(app_path),
                    str(zip_path),
                ],
                check=True,
            )
            print(f"Packaged macOS Zip Archive: {zip_path}")
        except (subprocess.SubprocessError, FileNotFoundError):
            shutil.make_archive("dist/TLS_to_FDS_macOS", "zip", root_dir="dist", base_dir="TLS_to_FDS.app")
            print(f"Packaged macOS Zip Archive (fallback): {zip_path}")

        # Package macOS Disk Image (.dmg) using native hdiutil
        dmg_path = Path("dist/TLS_to_FDS_macOS.dmg")
        if dmg_path.exists():
            dmg_path.unlink()
        try:
            print("Packaging macOS Disk Image (.dmg)...")
            subprocess.run(
                [
                    "hdiutil",
                    "create",
                    "-volname",
                    "TLS_to_FDS",
                    "-srcfolder",
                    str(app_path),
                    "-ov",
                    "-format",
                    "UDZO",
                    str(dmg_path),
                ],
                check=True,
            )
            print(f"Packaged macOS Disk Image: {dmg_path}")
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            print(f"Note: hdiutil not available or failed ({e}); skipping .dmg generation.")

    # 2. Standard directory (Windows / Linux / macOS folder)
    dist_dir = Path("dist/TLS_to_FDS")
    if dist_dir.exists() and presets_src.exists():
        dist_presets = dist_dir / "presets"
        dist_presets.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(presets_src, dist_presets, dirs_exist_ok=True)
        print(f"Copied presets directory to {dist_presets}")

    print("\nBuild complete! Check the 'dist' directory for output artifacts.")


if __name__ == "__main__":
    build()

