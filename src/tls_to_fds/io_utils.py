"""I/O Utilities for TLS_to_FDS.

Provides functions for loading global configuration defaults, reading forest combustion presets,
and exporting Fortran Binary Data (.bdf) voxel matrices for FDS simulation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import FortranFile


def safe_get(obj: Any, key: str, default: Any = None) -> Any:
    """Safely retrieves a configuration property from a dictionary or object attribute.

    Parameters
    ----------
    obj : Any
        Dictionary or dataclass object.
    key : str
        Property name to retrieve.
    default : Any, optional
        Default fallback value if property is missing or None.

    Returns
    -------
    Any
        Retrieved value or default.
    """
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_GLOBAL_DEFAULTS = None


def load_global_defaults() -> dict[str, Any]:
    """Loads default configuration values from default_config.json.

    Returns
    -------
    dict[str, Any]
        Dictionary of default application parameters.
    """
    global _GLOBAL_DEFAULTS
    if _GLOBAL_DEFAULTS is not None:
        return _GLOBAL_DEFAULTS

    config_path = Path(__file__).parent / "default_config.json"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as file:
            _GLOBAL_DEFAULTS = json.load(file)
    else:
        _GLOBAL_DEFAULTS = {}
    return _GLOBAL_DEFAULTS


def get_default(category: str, key: str, fallback: Any = None) -> Any:
    """Retrieves a specific default setting value from the global configuration.

    Parameters
    ----------
    category : str
        Configuration category key (e.g. 'domain_params', 'env_params').
    key : str
        Setting key within the category.
    fallback : Any, optional
        Fallback value if category or key is not present.

    Returns
    -------
    Any
        Configuration setting value or fallback.
    """
    defaults = load_global_defaults()
    cat_dict = defaults.get(category, {})
    return cat_dict.get(key, fallback)


def generate_fortran(
    name: str,
    array_2d: np.ndarray,
    voxel_size: float,
    bd: float | np.ndarray | list[float],
    output_dir: str | Path,
) -> None:
    """Exports a 3D vegetative voxel cluster to an FDS-compatible Fortran Binary Data (.bdf) file.

    Parameters
    ----------
    name : str
        Base file name (without extension).
    array_2d : np.ndarray
        (N, 3) or (N, >=3) array of voxel center spatial coordinates (X, Y, Z).
    voxel_size : float
        Cubic voxel cell dimension in meters.
    bd : float or np.ndarray or list of float
        Nominal bulk density (kg/m³) or 1D array of per-voxel bulk densities.
    output_dir : str or Path
        Destination directory path.

    Raises
    ------
    ValueError
        If voxel_size is non-positive or array_2d has invalid dimensions.
    FileNotFoundError
        If output_dir does not exist.
    """
    if voxel_size <= 0:
        raise ValueError(f"Voxel size must be strictly positive. Got: {voxel_size}")
    if array_2d.ndim != 2 or array_2d.shape[1] < 3:
        raise ValueError("Array must be 2D with at least X, Y, Z coordinate columns.")
    out_path = Path(output_dir)
    if not out_path.exists():
        raise FileNotFoundError(f"Output directory does not exist: {output_dir}")

    file_path = out_path / f"{name}.bdf"
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
    """Robustly locates the presets directory across source, MEIPASS, and executable contexts.

    Returns
    -------
    Path
        Absolute or relative Path object pointing to the presets/ directory.
    """
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


def load_preset(
    preset_name: str, presets_dir: str | Path | None = None
) -> dict[str, Any]:
    """Loads a forest biome combustion preset JSON file.

    Parameters
    ----------
    preset_name : str
        Name of the preset (e.g. 'ponderosa_pine_summer').
    presets_dir : str or Path, optional
        Custom directory path containing preset JSON files.

    Returns
    -------
    dict[str, Any]
        Parsed dictionary of preset fuel classes and thermal properties.

    Raises
    ------
    ValueError
        If preset_name is empty.
    FileNotFoundError
        If the preset JSON file does not exist.
    """
    if not preset_name or not str(preset_name).strip():
        raise ValueError("Preset name cannot be empty.")

    if presets_dir is None:
        presets_dir = get_presets_dir()

    # Sanitize preset name to prevent directory traversal
    clean_name = Path(str(preset_name).strip()).name
    preset_path = Path(presets_dir) / f"{clean_name}.json"

    if preset_path.exists():
        with open(preset_path, encoding="utf-8") as file:
            return json.load(file)
    else:
        raise FileNotFoundError(f"Preset file not found: {preset_path}")
