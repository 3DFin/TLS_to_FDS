import numpy as np
import json
from pathlib import Path
from scipy.io import FortranFile
from typing import Dict, Any, Union
import sys


def safe_get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_GLOBAL_DEFAULTS = None


def load_global_defaults() -> Dict[str, Any]:
    global _GLOBAL_DEFAULTS
    if _GLOBAL_DEFAULTS is not None:
        return _GLOBAL_DEFAULTS

    config_path = Path(__file__).parent / "default_config.json"
    if config_path.exists():
        with open(config_path, "r") as file:
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
    output_dir: Union[str, Path],
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

    for i in range(n):
        f.write_record(array_2d[i].astype(np.float64))
        f.write_record(np.array(bd, dtype=np.float64))
    f.close()


def get_presets_dir() -> Path:
    cwd_presets = Path.cwd() / "presets"
    if cwd_presets.exists():
        return cwd_presets
    if hasattr(sys, "_MEIPASS"):
        meipass_presets = Path(sys._MEIPASS) / "presets"
        if meipass_presets.exists():
            return meipass_presets
    return Path("presets")


def load_preset(preset_name: str, presets_dir: str = None) -> Dict[str, Any]:
    if presets_dir is None:
        presets_dir = get_presets_dir()
    assert preset_name, "Error: Preset name cannot be empty."
    preset_path = Path(presets_dir) / f"{preset_name}.json"

    if preset_path.exists():
        with open(preset_path, "r") as file:
            return json.load(file)
    else:
        raise FileNotFoundError(f"Preset file not found: {preset_path}")
