"""Spatial and Domain Decomposition Utilities for TLS_to_FDS.

Handles bounding box calculations, multi-mesh domain partitioning with boundary snapping,
and 2-stage voxelization for dynamic bulk density imputation.
"""

from typing import Any

import numpy as np
from dendroptimized import voxelize as vox

from .io_utils import get_default, safe_get


def get_global_min_max(datasets: list[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Calculates the unified minimum and maximum 3D coordinates across multiple point clouds.

    Parameters
    ----------
    datasets : list of np.ndarray
        List of point cloud arrays, each having shape (N, 3) or (N, >=3).

    Returns
    -------
    tuple of (np.ndarray, np.ndarray)
        Global minimum coordinates (Xmin, Ymin, Zmin) and maximum coordinates (Xmax, Ymax, Zmax).

    Raises
    ------
    ValueError
        If datasets list is empty or contains non-numpy arrays.
    """
    if not datasets:
        raise ValueError("The datasets list cannot be empty.")
    if not all(isinstance(d, np.ndarray) for d in datasets):
        raise ValueError("All elements in datasets must be numpy ndarrays.")

    min_coords = np.min([np.min(data, axis=0) for data in datasets], axis=0)
    max_coords = np.max([np.max(data, axis=0) for data in datasets], axis=0)
    return min_coords, max_coords


def calculate_nested_domain(
    raw_min: np.ndarray, raw_max: np.ndarray, domain_params: Any, base_voxel: float
) -> tuple[list[float], list[float], int, int, int]:
    """Calculates snapped computational domain bounds for nested base and sky meshes.

    Parameters
    ----------
    raw_min : np.ndarray
        Minimum coordinates (X, Y, Z) of the vegetation point cloud.
    raw_max : np.ndarray
        Maximum coordinates (X, Y, Z) of the vegetation point cloud.
    domain_params : Any
        Domain configuration dataclass or dictionary (lateral_pad, top_pad, mpi_x, mpi_y, sky_mult).
    base_voxel : float
        Base grid voxel resolution in meters.

    Returns
    -------
    base_bounds : list of float
        [xmin, ymin, zmin, xmax, ymax, zmax] bounding box for the fine base domain.
    sky_bounds : list of float
        [xmin, ymin, zmin, xmax, ymax, zmax] bounding box for the coarse sky mesh.
    nx, ny, nz : int
        Cell counts along X, Y, Z axes for the base mesh domain.
    """
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


def compute_dynamic_voxel_bulk_densities(
    raw_points: np.ndarray,
    voxel_size: float,
    nominal_bd: float,
    sub_voxel_size: float = 0.01,
    min_factor: float = 0.05,
    max_factor: float = 4.0,
) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:
    """Calculates spatially varying 3D bulk densities for fuel layer voxels using 2-stage micro-voxelization.

    Stage 1: Micro-voxelizes raw points at sub_voxel_size (default 1cm) to remove duplicate returns
             and scan overlap density inflation.
    Stage 2: Voxelizes unique micro-voxel centers at simulation voxel_size to obtain micro-voxel
             occupancy counts P_v per simulation voxel.
    Stage 3: Scales nominal bulk density by P_v / P_fl_bar, applies safety ratio bounds,
             and re-normalizes to preserve total dry fuel mass.

    Parameters
    ----------
    raw_points : np.ndarray
        Point cloud array of shape (N, 3) (X, Y, Z).
    voxel_size : float
        Target simulation voxel resolution in meters (e.g. 0.2 m).
    nominal_bd : float
        Nominal bulk density for the layer (kg/m3).
    sub_voxel_size : float, default 0.01
        Sub-voxel / micro-voxel resolution in meters (e.g. 0.01 m = 1 cm).
    min_factor : float, default 0.05
        Minimum allowed ratio relative to nominal_bd.
    max_factor : float, default 4.0
        Maximum allowed ratio relative to nominal_bd.

    Returns
    -------
    sim_voxel_coords : np.ndarray
        Array of shape (M, 3) containing (X, Y, Z) simulation voxel center coordinates.
    bd_array : np.ndarray
        Array of shape (M,) containing per-voxel bulk density values (kg/m3).
    stats : dict
        Dictionary of statistics (p_fl_bar, min_bd, max_bd, mean_bd, total_mass_ratio).
    """
    if len(raw_points) == 0:
        raise ValueError("raw_points array cannot be empty.")
    if voxel_size <= 0:
        raise ValueError(f"voxel_size must be strictly positive. Got: {voxel_size}")

    # Stage 1: Micro-voxelize raw points at sub_voxel_size (e.g. 1cm) to eliminate duplicate returns
    micro_data = vox(raw_points, sub_voxel_size, sub_voxel_size, with_n_points=False)[0]
    micro_coords = micro_data[:, :3]

    # Stage 2: Voxelize unique micro-voxel centers at target simulation voxel_size
    sim_data = vox(micro_coords, voxel_size, voxel_size, with_n_points=True)[0]
    sim_voxel_coords = sim_data[:, :3]
    p_v = sim_data[:, 3].astype(float)

    n_voxels = len(p_v)
    if n_voxels == 0 or np.sum(p_v) == 0:
        return (
            sim_voxel_coords,
            np.full(n_voxels, nominal_bd),
            {
                "p_fl_bar": 0.0,
                "min_bd": nominal_bd,
                "max_bd": nominal_bd,
                "mean_bd": nominal_bd,
                "total_mass_ratio": 1.0,
            },
        )

    # Stage 3: Compute mean occupancy P_fl_bar and raw density ratio P_v / P_fl_bar
    p_fl_bar = float(np.mean(p_v))
    raw_bd = nominal_bd * (p_v / p_fl_bar)

    # Stage 4: Apply safety clamping bounds
    min_bd_bound = nominal_bd * min_factor
    max_bd_bound = nominal_bd * max_factor
    clamped_bd = np.clip(raw_bd, min_bd_bound, max_bd_bound)

    # Stage 5: Mass-preserving re-normalization
    target_mass = n_voxels * nominal_bd
    current_mass = np.sum(clamped_bd)
    mass_ratio = target_mass / current_mass if current_mass > 0 else 1.0
    bd_final = clamped_bd * mass_ratio

    stats = {
        "p_fl_bar": p_fl_bar,
        "min_bd": float(np.min(bd_final)),
        "max_bd": float(np.max(bd_final)),
        "mean_bd": float(np.mean(bd_final)),
        "total_mass_ratio": float(mass_ratio),
    }

    return sim_voxel_coords, bd_final, stats
