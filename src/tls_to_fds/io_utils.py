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
    n = array_2d.shape[0]

    if n == 0:
        bounds = np.zeros(6, dtype=np.float64)
    else:
        x, y, z = array_2d[:, 0], array_2d[:, 1], array_2d[:, 2]
        bounds = np.array(
            [
                np.min(x) - voxel_size / 2,
                np.max(x) + voxel_size / 2,
                np.min(y) - voxel_size / 2,
                np.max(y) + voxel_size / 2,
                np.min(z) - voxel_size / 2,
                np.max(z) + voxel_size / 2,
            ],
            dtype=np.float64,
        )

    # Convert bulk density to 1D float64 array of length n
    if isinstance(bd, (np.ndarray, list)):
        bd_arr = np.asarray(bd, dtype=np.float64).ravel()
    else:
        bd_arr = np.full(n, float(bd), dtype=np.float64)

    coords = np.ascontiguousarray(array_2d[:, :3], dtype=np.float64)

    # Construct Fortran unformatted binary stream header:
    # Record 1: bounds (48 bytes) -> tag 48 (uint32), 6x float64, tag 48 (uint32)
    # Record 2: voxel_size (24 bytes) -> tag 24 (uint32), 3x float64, tag 24 (uint32)
    # Record 3: n (4 bytes) -> tag 4 (uint32), 1x int32, tag 4 (uint32)
    header = bytearray()

    tag48 = np.uint32(48).tobytes()
    header.extend(tag48)
    header.extend(bounds.tobytes())
    header.extend(tag48)

    tag24 = np.uint32(24).tobytes()
    vox_arr = np.array([voxel_size, voxel_size, voxel_size], dtype=np.float64)
    header.extend(tag24)
    header.extend(vox_arr.tobytes())
    header.extend(tag24)

    tag4 = np.uint32(4).tobytes()
    n_arr = np.int32(n)
    header.extend(tag4)
    header.extend(n_arr.tobytes())
    header.extend(tag4)

    # Vectorized body records for each voxel i:
    # Record coords: tag24 (4B) + 3x float64 (24B) + tag24 (4B) = 32B
    # Record bd:     tag8  (4B) + 1x float64 (8B)  + tag8  (4B) = 16B
    # Total per voxel = 48 bytes
    if n > 0:
        dtype_voxel = np.dtype(
            [
                ("tag_c1", "<u4"),
                ("coords", "<f8", (3,)),
                ("tag_c2", "<u4"),
                ("tag_b1", "<u4"),
                ("bd", "<f8"),
                ("tag_b2", "<u4"),
            ]
        )
        vox_table = np.empty(n, dtype=dtype_voxel)
        vox_table["tag_c1"] = 24
        vox_table["coords"] = coords
        vox_table["tag_c2"] = 24
        vox_table["tag_b1"] = 8
        vox_table["bd"] = bd_arr
        vox_table["tag_b2"] = 8
        body_bytes = vox_table.tobytes()
    else:
        body_bytes = b""

    with open(file_path, "wb") as f:
        f.write(header)
        if body_bytes:
            f.write(body_bytes)


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
