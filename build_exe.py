import os
import platform
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

        # Detect CPU Architecture on macOS (arm64 for Apple Silicon vs x86_64 for Intel)
        arch = platform.machine().lower()
        arch_suffix = "AppleSilicon" if arch in ("arm64", "aarch64") else "Intel"
        print(f"Detected macOS Target Architecture: {arch} ({arch_suffix})")

        # Package macOS .zip using ditto (preserves symlinks and resource forks)
        zip_name = f"TLS_to_FDS_macOS_{arch_suffix}.zip"
        zip_path = Path(f"dist/{zip_name}")
        generic_zip = Path("dist/TLS_to_FDS_macOS.zip")
        if zip_path.exists():
            zip_path.unlink()
        if generic_zip.exists():
            generic_zip.unlink()

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
            shutil.copyfile(zip_path, generic_zip)
            print(f"Packaged macOS Zip Archive: {zip_path} and {generic_zip}")
        except (subprocess.SubprocessError, FileNotFoundError):
            shutil.make_archive(f"dist/TLS_to_FDS_macOS_{arch_suffix}", "zip", root_dir="dist", base_dir="TLS_to_FDS.app")
            if zip_path.exists():
                shutil.copyfile(zip_path, generic_zip)
            print(f"Packaged macOS Zip Archive (fallback): {zip_path}")

        # Package macOS Disk Image (.dmg) using native hdiutil
        dmg_name = f"TLS_to_FDS_macOS_{arch_suffix}.dmg"
        dmg_path = Path(f"dist/{dmg_name}")
        generic_dmg = Path("dist/TLS_to_FDS_macOS.dmg")
        if dmg_path.exists():
            dmg_path.unlink()
        if generic_dmg.exists():
            generic_dmg.unlink()

        try:
            print(f"Packaging macOS Disk Image (.dmg) for {arch_suffix}...")
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
            shutil.copyfile(dmg_path, generic_dmg)
            print(f"Packaged macOS Disk Image: {dmg_path} and {generic_dmg}")
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

