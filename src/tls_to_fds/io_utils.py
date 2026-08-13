from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import FortranFile


def safe_get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_GLOBAL_DEFAULTS = None


def load_global_defaults() -> dict[str, Any]:
    global _GLOBAL_DEFAULTS
    if _GLOBAL_DEFAULTS is not None:
        return _GLOBAL_DEFAULTS

    config_path = Path(__file__).parent / "default_config.json"
    if config_path.exists():
        with open(config_path) as file:
            _GLOBAL_DEFAULTS = json.load(file)
    else:
        _GLOBAL_DEFAULTS = {}
    return _GLOBAL_DEFAULTS


def get_default(category: str, key: str, fallback: Any = None) -> Any:
    defaults = load_global_defaults()
    cat_dict = defaults.get(category, {})
    return cat_dict.get(key, fallback)


def generate_fortran(
    name: str,
    array_2d: np.ndarray,
    voxel_size: float,
    bd: float,
    output_dir: str | Path,
) -> None:
    assert voxel_size > 0, (
        f"Error: Voxel size must be strictly positive. Got: {voxel_size}"
    )
    assert array_2d.ndim == 2 and array_2d.shape[1] >= 3, (
        "Error: Array must be 2D with at least X, Y, Z columns."
    )
    assert Path(output_dir).exists(), (
        f"Error: Output directory does not exist: {output_dir}"
    )

    file_path = Path(output_dir) / f"{name}.bdf"
    f = FortranFile(file_path, "w")

    n = array_2d.shape[0]
    x, y, z = array_2d[:, 0], array_2d[:, 1], array_2d[:, 2]

    bounds = np.array(
        [
            min(x) - voxel_size / 2,
            max(x) + voxel_size / 2,
            min(y) - voxel_size / 2,
            max(y) + voxel_size / 2,
            min(z) - voxel_size / 2,
            max(z) + voxel_size / 2,
        ],
        dtype=np.float64,
    )

    f.write_record(bounds)
    f.write_record(np.array([voxel_size] * 3, dtype=np.float64))
    f.write_record(np.array(n, dtype=np.int32))

    is_bd_array = isinstance(bd, (np.ndarray, list))
    for i in range(n):
        f.write_record(array_2d[i, :3].astype(np.float64))
        local_bd = float(bd[i]) if is_bd_array else float(bd)
        f.write_record(np.array(local_bd, dtype=np.float64))
    f.close()


def get_presets_dir() -> Path:
    """Robustly locates the presets directory across source, MEIPASS, and executable contexts."""
    # 1. Bundled PyInstaller MEIPASS directory
    if hasattr(sys, "_MEIPASS"):
        meipass_presets = Path(sys._MEIPASS) / "presets"
        if meipass_presets.exists() and any(meipass_presets.glob("*.json")):
            return meipass_presets

    # 2. Next to executable if running as PyInstaller frozen exe
    if getattr(sys, "frozen", False):
        exe_presets = Path(sys.executable).parent / "presets"
        if exe_presets.exists() and any(exe_presets.glob("*.json")):
            return exe_presets

    # 3. Source repository location relative to io_utils.py (src/tls_to_fds/io_utils.py -> presets)
    source_presets = Path(__file__).resolve().parent.parent.parent / "presets"
    if source_presets.exists() and any(source_presets.glob("*.json")):
        return source_presets

    # 4. Current working directory presets/
    cwd_presets = Path.cwd() / "presets"
    if cwd_presets.exists() and any(cwd_presets.glob("*.json")):
        return cwd_presets

    # 5. Module directory relative presets/
    module_presets = Path(__file__).resolve().parent / "presets"
    if module_presets.exists() and any(module_presets.glob("*.json")):
        return module_presets

    # Fallback return
    if source_presets.exists():
        return source_presets
    if cwd_presets.exists():
        return cwd_presets
    return Path("presets")


def load_preset(preset_name: str, presets_dir: str | Path | None = None) -> dict[str, Any]:
    if presets_dir is None:
        presets_dir = get_presets_dir()
    assert preset_name, "Error: Preset name cannot be empty."
    preset_path = Path(presets_dir) / f"{preset_name}.json"

    if preset_path.exists():
        with open(preset_path, encoding="utf-8") as file:
            return json.load(file)
    else:
        raise FileNotFoundError(f"Preset file not found: {preset_path}")

