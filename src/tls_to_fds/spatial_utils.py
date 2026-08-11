from typing import Any

import numpy as np

from .io_utils import get_default, safe_get


def get_global_min_max(datasets: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    assert datasets, "Error: The datasets list cannot be empty."
    assert all(isinstance(d, np.ndarray) for d in datasets), (
        "Error: All datasets must be numpy arrays."
    )

    min_coords = np.min([np.min(data, axis=0) for data in datasets], axis=0)
    max_coords = np.max([np.max(data, axis=0) for data in datasets], axis=0)
    return min_coords, max_coords


def calculate_wedding_cake_domain(
    raw_min: np.ndarray, raw_max: np.ndarray, domain_params: Any, base_voxel: float
) -> tuple[list[float], list[float], int, int, int]:
    lateral_pad = safe_get(
        domain_params, "lateral_pad", get_default("domain_params", "lateral_pad", 10.0)
    )
    top_pad = safe_get(
        domain_params, "top_pad", get_default("domain_params", "top_pad", 20.0)
    )
    sky_mult = safe_get(
        domain_params,
        "sky_multiplier",
        get_default("domain_params", "sky_multiplier", 2),
    )
    mpi_x = safe_get(domain_params, "mpi_x", get_default("domain_params", "mpi_x", 2))
    mpi_y = safe_get(domain_params, "mpi_y", get_default("domain_params", "mpi_y", 3))

    snap_x = base_voxel * sky_mult * mpi_x
    snap_y = base_voxel * sky_mult * mpi_y
    snap_z = base_voxel * sky_mult

    x_min, y_min = raw_min[0] - lateral_pad, raw_min[1] - lateral_pad
    x_max, y_max = raw_max[0] + lateral_pad, raw_max[1] + lateral_pad

    z_min = 0.0
    base_z_max = raw_max[2]

    snap_x_min = np.floor(x_min / snap_x) * snap_x
    snap_y_min = np.floor(y_min / snap_y) * snap_y
    snap_x_max = np.ceil(x_max / snap_x) * snap_x
    snap_y_max = np.ceil(y_max / snap_y) * snap_y

    snap_base_z_max = np.ceil(base_z_max / snap_z) * snap_z
    snap_sky_z_max = snap_base_z_max + (np.ceil(top_pad / snap_z) * snap_z)

    base_bounds = [
        snap_x_min,
        snap_y_min,
        z_min,
        snap_x_max,
        snap_y_max,
        snap_base_z_max,
    ]
    sky_bounds = [
        snap_x_min,
        snap_y_min,
        snap_base_z_max,
        snap_x_max,
        snap_y_max,
        snap_sky_z_max,
    ]

    nx = round((snap_x_max - snap_x_min) / base_voxel)
    ny = round((snap_y_max - snap_y_min) / base_voxel)
    nz = round((snap_base_z_max - z_min) / base_voxel)

    return base_bounds, sky_bounds, nx, ny, nz
