"""
Computational Benchmarking Suite for TLS_to_FDS
================================================
Scientific benchmark script quantifying computation times, memory-mapped Fortran binary
throughput, and 1D Boundary Fuel Model (BFM) ground fuel discretization scalability for the
accompanying Application Note in Computers and Electronics in Agriculture (Elsevier).

Dataset: Real Terrestrial Laser Scanning (TLS) point clouds from a 40x40 m2 Pinus ponderosa
forest plot in Sycan Marsh, Oregon, USA (test_ladder_fuels.laz and test_surface_fuels.laz: ~5M pts).
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

import laspy
import matplotlib.pyplot as plt
import numpy as np

# Ensure UTF-8 output on Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure src is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from tls_to_fds import fds_builder, io_utils, litter_models, spatial_utils
from tls_to_fds.models import DomainParams, EnvParams, GroundFuels, OutputParams


def get_system_metadata() -> dict[str, Any]:
    """Captures hardware and software environment details for scientific reproducibility."""
    import scipy

    return {
        "os": platform.platform(),
        "processor": platform.processor(),
        "cpu_count_logical": os.cpu_count(),
        "python_version": sys.version.split()[0],
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "laspy_version": laspy.__version__,
        "plot_location": "Sycan Marsh, Oregon, USA (40x40 m2 Pinus ponderosa plot)",
    }


def load_real_datasets(
    data_dir: Path,
) -> tuple[list[np.ndarray], list[str], list[float], np.ndarray]:
    """Loads real Sycan Marsh Pinus ponderosa TLS point clouds."""
    cloud_files = [
        ("test_ladder_fuels.laz", "Canopy layer", 1.5),
        ("test_surface_fuels.laz", "Surface layer", 0.8),
    ]
    datasets = []
    names = []
    nominal_bds = []

    for fname, layer_name, bd in cloud_files:
        p = data_dir / fname
        if not p.exists():
            raise FileNotFoundError(f"Missing required real TLS dataset: {p}")
        las = laspy.read(p)
        pts = np.column_stack((las.x, las.y, las.z))
        datasets.append(pts)
        names.append(layer_name)
        nominal_bds.append(bd)

    # Global min normalization
    raw_min, _ = spatial_utils.get_global_min_max(datasets)
    translated_datasets = [d - raw_min for d in datasets]
    return translated_datasets, names, nominal_bds, raw_min


# ==============================================================================
# EXPERIMENT 1: 3D GRID SCALING (Δx)
# ==============================================================================
def benchmark_voxel_scaling(
    datasets: list[np.ndarray],
    names: list[str],
    nominal_bds: list[float],
    resolutions: list[float],
    repeats: int = 3,
    output_temp_dir: Path = Path("benchmark_results/scratch"),
) -> list[dict[str, Any]]:
    """Benchmarks 3D voxelization, Fortran BDF write throughput, and master FDS generation

    across computational grid cell resolutions (Δx).
    """
    output_temp_dir.mkdir(parents=True, exist_ok=True)
    results = []
    preset = io_utils.load_preset("ponderosa_pine_summer")

    domain_params = DomainParams(
        lateral_pad=4.0,
        top_pad=6.0,
        sky_multiplier=2,
        mpi_x=2,
        mpi_y=2,
    )
    env_params = EnvParams(
        sim_time=60.0,
        wind_dev_time=10.0,
        wind_dir=0.0,
        wind_speed=3.0,
        hrrpua=500.0,
        track_embers=False,
        ign_duration=20.0,
        obukhov=-300.0,
        z0=0.1,
        ember_density=60.0,
        ember_velocity=0.0,
        ign_pattern="Line",
        vent_width=1.0,
    )
    ground_fuels = GroundFuels(
        litter_active=True,
        litter_depth=0.05,
        litter_bd=15.0,
        litter_moisture=0.10,
        litter_model_mode="Uniform",
    )
    output_params = OutputParams(
        hrrpua=True,
        flame=True,
        temp=True,
        wind=True,
        biomass=True,
    )

    print("\n--- EXPERIMENT 1: 3D Voxel Resolution & Fortran BDF Scaling ---")
    print(f"Testing resolutions: {resolutions} m | Repeats: {repeats}")

    for vox_size in resolutions:
        print(f"\nEvaluating voxel size dx = {vox_size:.2f} m...")

        vox_times = []
        bdf_times = []
        fds_times = []
        total_times = []
        vox_counts = []
        bdf_bytes_list = []

        # Warmup run
        _ = spatial_utils.compute_dynamic_voxel_bulk_densities(
            datasets[0], vox_size, nominal_bds[0]
        )

        for rep in range(repeats):
            t_start = time.perf_counter()

            # 1. 3D Voxelization (Dynamic BD with Stage 1 micro-voxelization at 1 cm)
            t_vox_start = time.perf_counter()
            voxels = []
            final_bds = []
            for d, bd_nom in zip(datasets, nominal_bds):
                sim_coords, bd_array, _ = (
                    spatial_utils.compute_dynamic_voxel_bulk_densities(
                        d, vox_size, nominal_bd=bd_nom
                    )
                )
                voxels.append(sim_coords)
                final_bds.append(bd_array)
            t_vox = time.perf_counter() - t_vox_start

            total_voxels = sum(len(v) for v in voxels)

            # 2. Domain Decomposition & Bounds Calculation
            translated_min, translated_max = spatial_utils.get_global_min_max(voxels)
            forest_bounds = [
                translated_min[0] - vox_size / 2.0,
                translated_min[1] - vox_size / 2.0,
                0.0,
                translated_max[0] + vox_size / 2.0,
                translated_max[1] + vox_size / 2.0,
                translated_max[2] + vox_size / 2.0,
            ]
            base_bounds, sky_bounds, nx, ny, nz = spatial_utils.calculate_nested_domain(
                translated_min, translated_max, domain_params, vox_size
            )

            # 3. Fortran BDF Zero-Copy Memory Stream Export
            t_bdf_start = time.perf_counter()
            bdf_bytes = 0
            for idx, (layer_name, vox_data, bd_val) in enumerate(
                zip(names, voxels, final_bds)
            ):
                bdf_path = (
                    output_temp_dir
                    / f"bench_{layer_name.replace(' ', '_')}_{vox_size}.bdf"
                )
                io_utils.generate_fortran(
                    bdf_path.stem, vox_data, vox_size, bd_val, output_temp_dir
                )
                if bdf_path.exists():
                    bdf_bytes += bdf_path.stat().st_size
            t_bdf = time.perf_counter() - t_bdf_start

            # 4. Master .fds namelist script generation
            t_fds_start = time.perf_counter()
            fuel_layers_cfg = [
                {"filename": f"layer_{i}.las", "bulk_density": bd, "dynamic_bd": True}
                for i, bd in enumerate(nominal_bds)
            ]
            fds_builder.assemble_fds_file(
                output_dir=output_temp_dir,
                sim_name=f"bench_dx_{vox_size}",
                base_bounds=base_bounds,
                sky_bounds=sky_bounds,
                forest_bounds=forest_bounds,
                nx=nx,
                ny=ny,
                nz=nz,
                fuel_layers=fuel_layers_cfg,
                active_preset=preset,
                env_params=env_params,
                ground_fuels=ground_fuels,
                output_params=output_params,
                domain_params=domain_params,
                base_voxel=vox_size,
                litter_surfs=None,
                litter_vents=None,
            )
            t_fds = time.perf_counter() - t_fds_start
            t_total = time.perf_counter() - t_start

            vox_times.append(t_vox)
            bdf_times.append(t_bdf)
            fds_times.append(t_fds)
            total_times.append(t_total)
            vox_counts.append(total_voxels)
            bdf_bytes_list.append(bdf_bytes)

        mean_voxels = int(np.mean(vox_counts))
        mean_vox_time = float(np.mean(vox_times))
        std_vox_time = float(np.std(vox_times))
        mean_bdf_time = float(np.mean(bdf_times)) * 1000.0  # to ms
        std_bdf_time = float(np.std(bdf_times)) * 1000.0
        mean_fds_time = float(np.mean(fds_times)) * 1000.0  # to ms
        mean_total_time = float(np.mean(total_times))
        std_total_time = float(np.std(total_times))

        # Throughput
        bdf_throughput_m_vox_sec = (
            (mean_voxels / (np.mean(bdf_times))) / 1e6
            if np.mean(bdf_times) > 0
            else 0.0
        )
        bdf_mb_sec = (
            (np.mean(bdf_bytes_list) / (1024**2)) / np.mean(bdf_times)
            if np.mean(bdf_times) > 0
            else 0.0
        )

        print(
            f"   -> Voxels: {mean_voxels:,} | Vox Time: {mean_vox_time:.3f} +/- {std_vox_time:.3f} s "
            f"| BDF Time: {mean_bdf_time:.2f} +/- {std_bdf_time:.2f} ms ({bdf_throughput_m_vox_sec:.2f} M vox/s, {bdf_mb_sec:.1f} MB/s) "
            f"| Total: {mean_total_time:.3f} s"
        )

        results.append(
            {
                "voxel_size_m": vox_size,
                "active_voxels": mean_voxels,
                "voxelization_time_s": mean_vox_time,
                "voxelization_time_std_s": std_vox_time,
                "bdf_write_time_ms": mean_bdf_time,
                "bdf_write_time_std_ms": std_bdf_time,
                "bdf_throughput_m_vox_s": bdf_throughput_m_vox_sec,
                "bdf_throughput_mb_s": bdf_mb_sec,
                "fds_assembly_time_ms": mean_fds_time,
                "total_time_s": mean_total_time,
                "total_time_std_s": std_total_time,
            }
        )

    return results


# ==============================================================================
# EXPERIMENT 2: 1D BOUNDARY FUEL MODEL (BFM) LITTER SCALING (N_bins)
# ==============================================================================
def benchmark_litter_scaling(
    datasets: list[np.ndarray],
    data_dir: Path,
    bins_list: list[int],
    voxel_size: float = 0.20,
    repeats: int = 3,
    output_temp_dir: Path = Path("benchmark_results/scratch"),
) -> list[dict[str, Any]]:
    """Benchmarks Model 1 (Tree Distance Decay) and Model 2 (Canopy Turnover + Gaussian Dispersion)

    across discrete BFM quantization bin counts (N_bins).
    """
    output_temp_dir.mkdir(parents=True, exist_ok=True)
    results = []
    preset = io_utils.load_preset("ponderosa_pine_summer")

    # Establish common plot bounds from real dataset
    canopy_pts = datasets[0]
    translated_min, translated_max = spatial_utils.get_global_min_max([canopy_pts])
    domain_params = DomainParams(
        lateral_pad=4.0, top_pad=6.0, sky_multiplier=2, mpi_x=2, mpi_y=2
    )
    base_bounds, sky_bounds, nx, ny, nz = spatial_utils.calculate_nested_domain(
        translated_min, translated_max, domain_params, voxel_size
    )
    forest_bounds = [
        translated_min[0] - voxel_size / 2.0,
        translated_min[1] - voxel_size / 2.0,
        0.0,
        translated_max[0] + voxel_size / 2.0,
        translated_max[1] + voxel_size / 2.0,
        translated_max[2] + voxel_size / 2.0,
    ]
    grid_bounds_2d = (base_bounds[0], base_bounds[1], base_bounds[3], base_bounds[4])

    # Tree stems for Model 1: load real trunks or stem coordinates
    trunks_path = data_dir / "test_trunks.laz"
    if trunks_path.exists():
        loaded_trunks = litter_models.load_tree_map(trunks_path)
        # Pick 15 well-distributed trunk locations across the plot
        tree_stems = loaded_trunks[:: max(1, len(loaded_trunks) // 25)][:, :2]
        # Translate to local domain origin
        raw_min = np.min(canopy_pts, axis=0)[:2]
        tree_stems = tree_stems - raw_min
    else:
        # Fallback synthetic stem grid
        tree_stems = np.array([[10.0, 10.0], [20.0, 15.0], [15.0, 30.0], [30.0, 25.0]])

    # Pre-voxelize canopy for Model 2
    from dendroptimized import voxelize as vox

    coords_canopy = vox(canopy_pts, voxel_size, voxel_size, with_n_points=False)[0]
    v_grid_counts = np.zeros((nz, ny, nx), dtype=float)
    i_idx = np.clip(
        ((coords_canopy[:, 0] - base_bounds[0]) / voxel_size).astype(int), 0, nx - 1
    )
    j_idx = np.clip(
        ((coords_canopy[:, 1] - base_bounds[1]) / voxel_size).astype(int), 0, ny - 1
    )
    k_idx = np.clip(
        ((coords_canopy[:, 2] - base_bounds[2]) / voxel_size).astype(int), 0, nz - 1
    )
    np.add.at(v_grid_counts, (k_idx, j_idx, i_idx), 1.0)

    print("\n--- EXPERIMENT 2: Ground Fuel Litter Discretization Scaling ---")
    print(
        f"Testing BFM Bins: {bins_list} | Grid Cells: {nx} x {ny} = {nx * ny:,} cells | Repeats: {repeats}"
    )

    models_to_test = [
        ("Model 1 (Distance Decay)", 1),
        ("Model 2 (Canopy Turnover + Dispersion)", 2),
    ]

    for model_name, model_type in models_to_test:
        print(f"\nBenchmarking {model_name}...")

        for n_bins in bins_list:
            field_times = []
            tile_times = []
            fds_times = []
            vent_counts = []
            fds_sizes_kb = []

            for rep in range(repeats):
                # 1. Continuous Field Calculation
                t_field_start = time.perf_counter()
                if model_type == 1:
                    m1 = litter_models.TreeDistanceLitterModel(
                        tree_stems=tree_stems,
                        base_bulk_density=18.0,
                        min_bulk_density=2.5,
                        alpha=0.45,
                    )
                    litter_2d = m1.compute_litter_distribution(
                        grid_bounds_2d, (voxel_size, voxel_size)
                    )
                else:
                    m2 = litter_models.CanopyTurnoverLitterModel(
                        turnover_rate=0.20,
                        accumulation_time=3.0,
                        dispersion_sigma=1.5,
                        decomposition_rate=0.15,
                        consumption_rate=1.0,
                    )
                    # Convert load (kg/m2) to bulk density (kg/m3) for standard depth 0.05m
                    load_2d = m2.compute_litter_distribution(
                        v_grid_counts,
                        (voxel_size, voxel_size, voxel_size),
                        nominal_canopy_bd=1.5,
                    )
                    litter_2d = load_2d / 0.05

                t_field = (time.perf_counter() - t_field_start) * 1000.0  # ms

                # 2. Row-Merge & &VENT Tiling
                t_tile_start = time.perf_counter()
                surfs, vents = litter_models.build_litter_bfm_tiles(
                    litter_2d=litter_2d,
                    domain_bounds=base_bounds,
                    voxel_sizes=(voxel_size, voxel_size, voxel_size),
                    litter_depth=0.05,
                    litter_moisture=0.10,
                    sv_ratio=6000.0,
                    num_bins=n_bins,
                    merge_2d=True,
                )
                t_tile = (time.perf_counter() - t_tile_start) * 1000.0  # ms

                # 3. Master .fds Generation with BFM VENTs
                t_fds_start = time.perf_counter()
                sim_name = f"bench_litter_m{model_type}_b{n_bins}"
                fds_builder.assemble_fds_file(
                    output_dir=output_temp_dir,
                    sim_name=sim_name,
                    base_bounds=base_bounds,
                    sky_bounds=sky_bounds,
                    forest_bounds=forest_bounds,
                    nx=nx,
                    ny=ny,
                    nz=nz,
                    fuel_layers=[{"filename": "canopy.las", "bulk_density": 1.5}],
                    active_preset=preset,
                    env_params=EnvParams(
                        sim_time=60.0,
                        wind_dev_time=10.0,
                        wind_dir=0.0,
                        wind_speed=2.0,
                        hrrpua=500.0,
                        track_embers=False,
                        ign_duration=20.0,
                        obukhov=-300.0,
                        z0=0.1,
                        ember_density=60.0,
                        ember_velocity=0.0,
                        ign_pattern="Line",
                        vent_width=1.0,
                    ),
                    ground_fuels=GroundFuels(
                        litter_active=True,
                        litter_depth=0.05,
                        litter_bd=15.0,
                        litter_moisture=0.10,
                        num_litter_bins=n_bins,
                    ),
                    output_params=OutputParams(
                        hrrpua=True, flame=True, temp=True, wind=True, biomass=True
                    ),
                    domain_params=domain_params,
                    base_voxel=voxel_size,
                    litter_surfs=surfs,
                    litter_vents=vents,
                )
                t_fds = (time.perf_counter() - t_fds_start) * 1000.0  # ms
                fds_out_path = Path(output_temp_dir) / f"{sim_name}.fds"
                fds_size_kb = fds_out_path.stat().st_size / 1024.0

                field_times.append(t_field)
                tile_times.append(t_tile)
                fds_times.append(t_fds)
                vent_counts.append(len(vents))
                fds_sizes_kb.append(fds_size_kb)

            m_field = float(np.mean(field_times))
            m_tile = float(np.mean(tile_times))
            m_fds = float(np.mean(fds_times))
            m_vents = int(np.mean(vent_counts))
            m_size = float(np.mean(fds_sizes_kb))
            total_litter_ms = m_field + m_tile

            print(
                f"   [N_bins = {n_bins:3d}] Field: {m_field:6.2f} ms | Tiling: {m_tile:6.2f} ms "
                f"| &VENTs: {m_vents:5d} (Compression: {100.0 * (1.0 - m_vents / (nx * ny)):.1f}%) "
                f"| FDS Deck: {m_size:6.1f} KB | Total: {total_litter_ms:6.2f} ms"
            )

            results.append(
                {
                    "model": model_name,
                    "model_type": model_type,
                    "num_bins": n_bins,
                    "field_time_ms": m_field,
                    "tiling_time_ms": m_tile,
                    "total_litter_ms": total_litter_ms,
                    "vent_count": m_vents,
                    "fds_time_ms": m_fds,
                    "fds_size_kb": m_size,
                }
            )

    return results


# ==============================================================================
# EXPERIMENT 3: STAGE-BY-STAGE TIME BUDGET
# ==============================================================================
def benchmark_runtime_budget(
    data_dir: Path,
    voxel_size: float = 0.20,
    repeats: int = 3,
    output_temp_dir: Path = Path("benchmark_results/scratch"),
) -> dict[str, float]:
    """Profiles the computational time budget across each distinct stage on a canonical setup

    (Δx = 0.20 m, ~5M points, Model 2 Canopy Turnover with 10 bins).
    """
    output_temp_dir.mkdir(parents=True, exist_ok=True)
    preset = io_utils.load_preset("ponderosa_pine_summer")
    cloud_files = [
        (data_dir / "test_ladder_fuels.laz", "Canopy layer", 1.5),
        (data_dir / "test_surface_fuels.laz", "Surface layer", 0.8),
    ]

    t_io_list = []
    t_vox_list = []
    t_bdf_list = []
    t_litter_list = []
    t_fds_list = []

    for _ in range(repeats):
        # Stage 1: LiDAR I/O & Coordinate Translation
        t0 = time.perf_counter()
        raw_datasets = []
        names = []
        bds = []
        for path, name, bd in cloud_files:
            las = laspy.read(path)
            raw_datasets.append(np.column_stack((las.x, las.y, las.z)))
            names.append(name)
            bds.append(bd)
        raw_min, _ = spatial_utils.get_global_min_max(raw_datasets)
        datasets = [d - raw_min for d in raw_datasets]
        t_io = time.perf_counter() - t0

        # Stage 2: 3D Voxelization (2-Stage Dynamic Micro-Voxelization)
        t0 = time.perf_counter()
        voxels = []
        final_bds = []
        for d, bd in zip(datasets, bds):
            coords, bd_arr, _ = spatial_utils.compute_dynamic_voxel_bulk_densities(
                d, voxel_size, bd
            )
            voxels.append(coords)
            final_bds.append(bd_arr)
        t_vox = time.perf_counter() - t0

        # Domain calculation
        translated_min, translated_max = spatial_utils.get_global_min_max(voxels)
        domain_params = DomainParams(
            lateral_pad=4.0, top_pad=6.0, sky_multiplier=2, mpi_x=2, mpi_y=2
        )
        base_bounds, sky_bounds, nx, ny, nz = spatial_utils.calculate_nested_domain(
            translated_min, translated_max, domain_params, voxel_size
        )
        forest_bounds = [
            translated_min[0] - voxel_size / 2.0,
            translated_min[1] - voxel_size / 2.0,
            0.0,
            translated_max[0] + voxel_size / 2.0,
            translated_max[1] + voxel_size / 2.0,
            translated_max[2] + voxel_size / 2.0,
        ]

        # Stage 3: Fortran BDF Stream Export
        t0 = time.perf_counter()
        for name, v_data, bd_val in zip(names, voxels, final_bds):
            io_utils.generate_fortran(
                name.replace(" ", "_"), v_data, voxel_size, bd_val, output_temp_dir
            )
        t_bdf = time.perf_counter() - t0

        # Stage 4: Ground Fuel Litter Discretization & Spatial Rasters
        t0 = time.perf_counter()
        m2 = litter_models.CanopyTurnoverLitterModel(
            turnover_rate=0.20, accumulation_time=3.0, dispersion_sigma=1.5
        )
        # Canopy point count grid for Model 2
        canopy_vox = voxels[0]
        v_grid_counts = np.zeros((nz, ny, nx), dtype=float)
        i_idx = np.clip(
            ((canopy_vox[:, 0] - base_bounds[0]) / voxel_size).astype(int), 0, nx - 1
        )
        j_idx = np.clip(
            ((canopy_vox[:, 1] - base_bounds[1]) / voxel_size).astype(int), 0, ny - 1
        )
        k_idx = np.clip(
            ((canopy_vox[:, 2] - base_bounds[2]) / voxel_size).astype(int), 0, nz - 1
        )
        np.add.at(v_grid_counts, (k_idx, j_idx, i_idx), 10.0)
        load_2d = m2.compute_litter_distribution(
            v_grid_counts, (voxel_size, voxel_size, voxel_size), nominal_canopy_bd=1.5
        )
        litter_2d = load_2d / 0.05
        surfs, vents = litter_models.build_litter_bfm_tiles(
            litter_2d=litter_2d,
            domain_bounds=base_bounds,
            voxel_sizes=(voxel_size, voxel_size, voxel_size),
            litter_depth=0.05,
            num_bins=10,
            merge_2d=True,
        )
        t_litter = time.perf_counter() - t0

        # Stage 5: FDS Master Script Assembly
        t0 = time.perf_counter()
        fds_builder.assemble_fds_file(
            output_dir=output_temp_dir,
            sim_name="canonical_budget",
            base_bounds=base_bounds,
            sky_bounds=sky_bounds,
            forest_bounds=forest_bounds,
            nx=nx,
            ny=ny,
            nz=nz,
            fuel_layers=[
                {"filename": f"{n}.las", "bulk_density": bd}
                for n, bd in zip(names, bds)
            ],
            active_preset=preset,
            env_params=EnvParams(
                sim_time=60.0,
                wind_dev_time=10.0,
                wind_dir=0.0,
                wind_speed=2.0,
                hrrpua=500.0,
                track_embers=False,
                ign_duration=20.0,
                obukhov=-300.0,
                z0=0.1,
                ember_density=60.0,
                ember_velocity=0.0,
                ign_pattern="Line",
                vent_width=1.0,
            ),
            ground_fuels=GroundFuels(
                litter_active=True,
                litter_depth=0.05,
                litter_bd=15.0,
                litter_moisture=0.10,
                num_litter_bins=10,
            ),
            output_params=OutputParams(
                hrrpua=True, flame=True, temp=True, wind=True, biomass=True
            ),
            domain_params=domain_params,
            base_voxel=voxel_size,
            litter_surfs=surfs,
            litter_vents=vents,
        )
        t_fds = time.perf_counter() - t0

        t_io_list.append(t_io)
        t_vox_list.append(t_vox)
        t_bdf_list.append(t_bdf)
        t_litter_list.append(t_litter)
        t_fds_list.append(t_fds)

    budget = {
        "Point Cloud I/O (4.95M pts)": float(np.mean(t_io_list)),
        "3D Dynamic Voxelization (1cm -> 0.20m)": float(np.mean(t_vox_list)),
        "Fortran .bdf Stream Write": float(np.mean(t_bdf_list)),
        "Litter BFM Discretization & Tiling": float(np.mean(t_litter_list)),
        "FDS Master Script Assembly": float(np.mean(t_fds_list)),
    }
    return budget


# ==============================================================================
# EXPORT HELPERS (CSV, LATEX, PUBLICATION PLOTS)
# ==============================================================================
def export_latex_tables(
    results_vox: list[dict[str, Any]],
    results_litter: list[dict[str, Any]],
    budget: dict[str, float],
    out_dir: Path,
):
    """Exports formatted LaTeX tables using the booktabs package for direct inclusion in the manuscript."""
    # Table 1: Voxel scaling
    t1_lines = [
        "% Table 1: Multi-resolution computational performance and BDF streaming efficiency",
        "\\begin{table}[htbp]",
        "\\centering",
        "\\caption{Computational scalability and vectorized Fortran Binary Data (\\texttt{.bdf}) streaming throughput across simulation grid cell resolutions ($\\Delta x$) for the Sycan Marsh \\textit{Pinus ponderosa} plot (4,951,646 raw TLS points). Values represent mean $\\pm$ standard deviation across 3 independent trials.}",
        "\\label{tab:voxel_scaling}",
        "\\small",
        "\\begin{tabular}{ccccccc}",
        "\\toprule",
        "\\textbf{Resolution} & \\textbf{Active Voxels} & \\textbf{Voxelization} & \\textbf{BDF Write} & \\textbf{Throughput} & \\textbf{Throughput} & \\textbf{Total Pipeline} \\\\",
        "$\\Delta x$ (m) & $N_{\\text{vox}}$ & $t_{\\text{vox}}$ (s) & $t_{\\text{bdf}}$ (ms) & ($10^6$ vox/s) & (MB/s) & $t_{\\text{total}}$ (s) \\\\",
        "\\midrule",
    ]
    for r in results_vox:
        line = (
            f"{r['voxel_size_m']:.2f} & {r['active_voxels']:,} & "
            f"{r['voxelization_time_s']:.3f} $\\pm$ {r['voxelization_time_std_s']:.3f} & "
            f"{r['bdf_write_time_ms']:.2f} $\\pm$ {r['bdf_write_time_std_ms']:.2f} & "
            f"{r['bdf_throughput_m_vox_s']:.2f} & {r['bdf_throughput_mb_s']:.1f} & "
            f"{r['total_time_s']:.3f} $\\pm$ {r['total_time_std_s']:.3f} \\\\"
        )
        t1_lines.append(line)
    t1_lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}\n"])

    (out_dir / "table1_voxel_scaling.tex").write_text(
        "\n".join(t1_lines), encoding="utf-8"
    )

    # Table 2: Litter scaling
    t2_lines = [
        "% Table 2: Ground fuel BFM litter discretization performance",
        "\\begin{table}[htbp]",
        "\\centering",
        "\\caption{1D Boundary Fuel Model (BFM) ground litter layer discretization benchmarks for Model 1 (Tree distance decay) and Model 2 (Canopy turnover with 2D Gaussian wind dispersion) across discrete quantization bins ($N_{\\text{bins}}$) on a $0.20$~m computational grid.}",
        "\\label{tab:litter_scaling}",
        "\\small",
        "\\begin{tabular}{lcccccc}",
        "\\toprule",
        "\\textbf{Model} & $N_{\\text{bins}}$ & \\textbf{Field Calc.} & \\textbf{Tiling} & \\textbf{Resulting} & \\textbf{Compression} & \\textbf{FDS Deck} \\\\",
        "& & $t_{\\text{field}}$ (ms) & $t_{\\text{tile}}$ (ms) & \\&VENT Tiles & Ratio (\\%) & Size (KB) \\\\",
        "\\midrule",
    ]
    for r in results_litter:
        # Calculate compression ratio against raw cell grid (e.g. ~40,000 cells)
        comp_ratio = max(0.0, 100.0 * (1.0 - r["vent_count"] / 40000.0))
        line = (
            f"{r['model'].split('(')[0].strip()} & {r['num_bins']} & "
            f"{r['field_time_ms']:.2f} & {r['tiling_time_ms']:.2f} & "
            f"{r['vent_count']:,} & {comp_ratio:.1f}\\% & "
            f"{r['fds_size_kb']:.1f} \\\\"
        )
        t2_lines.append(line)
    t2_lines.extend(["\\bottomrule", "\\end{tabular}", "\\end{table}\n"])

    (out_dir / "table2_litter_scaling.tex").write_text(
        "\n".join(t2_lines), encoding="utf-8"
    )

    # Table 3: Runtime budget
    total_b = sum(budget.values())
    t3_lines = [
        "% Table 3: Stage-by-stage computational runtime budget",
        "\\begin{table}[htbp]",
        "\\centering",
        "\\caption{Stage-by-stage computational time budget for a canonical wildland fire simulation domain conversion ($\\Delta x = 0.20$~m, 4.95M raw TLS points, Model 2 ground fuels with $N_{\\text{bins}} = 10$).}",
        "\\label{tab:runtime_budget}",
        "\\small",
        "\\begin{tabular}{lcc}",
        "\\toprule",
        "\\textbf{Conversion Pipeline Stage} & \\textbf{Time (s)} & \\textbf{Fraction (\\%)} \\\\",
        "\\midrule",
    ]
    for stage, t_val in budget.items():
        frac = (t_val / total_b) * 100.0
        t3_lines.append(f"{stage} & {t_val:.3f} & {frac:.1f}\\% \\\\")
    t3_lines.extend(
        [
            "\\midrule",
            f"\\textbf{{Total Execution Time}} & \\textbf{{{total_b:.3f}}} & \\textbf{{100.0\\%}} \\\\",
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table}\n",
        ]
    )
    (out_dir / "table3_runtime_budget.tex").write_text(
        "\n".join(t3_lines), encoding="utf-8"
    )


def export_csv_tables(
    results_vox: list[dict[str, Any]],
    results_litter: list[dict[str, Any]],
    budget: dict[str, float],
    out_dir: Path,
):
    """Exports raw numerical metrics as CSV files."""
    import csv

    # Table 1
    with open(
        out_dir / "table1_voxel_scaling.csv", "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(f, fieldnames=list(results_vox[0].keys()))
        writer.writeheader()
        writer.writerows(results_vox)

    # Table 2
    with open(
        out_dir / "table2_litter_scaling.csv", "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.DictWriter(f, fieldnames=list(results_litter[0].keys()))
        writer.writeheader()
        writer.writerows(results_litter)

    # Table 3
    with open(
        out_dir / "table3_runtime_budget.csv", "w", newline="", encoding="utf-8"
    ) as f:
        writer = csv.writer(f)
        writer.writerow(["stage", "time_seconds", "percentage"])
        total_b = sum(budget.values())
        for stage, t_val in budget.items():
            writer.writerow([stage, f"{t_val:.4f}", f"{(t_val / total_b) * 100.0:.2f}"])


def generate_publication_figure(
    results_vox: list[dict[str, Any]],
    results_litter: list[dict[str, Any]],
    budget: dict[str, float],
    out_dir: Path,
):
    """Generates Elsevier COMPAG publication-quality multi-panel vector and raster figures."""
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9.0,
            "axes.labelsize": 9.5,
            "axes.titlesize": 10.0,
            "xtick.labelsize": 8.0,
            "ytick.labelsize": 8.0,
            "legend.fontsize": 8.0,
            "figure.titlesize": 11.5,
        }
    )

    fig, axes = plt.subplots(2, 2, figsize=(14.0, 9.2), dpi=300)
    fig.subplots_adjust(
        wspace=0.52, hspace=0.32, top=0.92, bottom=0.08, left=0.07, right=0.95
    )

    # -------------------------------------------------------------
    # Panel (a): 3D Voxel Scaling
    # -------------------------------------------------------------
    ax_a = axes[0, 0]
    ax_a.set_title(
        "(a) Computational Scaling vs. Voxel Resolution $\\Delta x$",
        fontweight="bold",
        pad=8,
    )
    dx_vals = [r["voxel_size_m"] for r in results_vox]
    vox_counts = [r["active_voxels"] for r in results_vox]
    vox_times = [r["voxelization_time_s"] for r in results_vox]
    total_times = [r["total_time_s"] for r in results_vox]

    ax_a.set_xlabel("Voxel Resolution $\\Delta x$ (m)")
    ax_a.set_ylabel("Execution Time (s)", color="#1b5e20")
    line1 = ax_a.plot(
        dx_vals,
        total_times,
        "o-",
        color="#2e7d32",
        linewidth=2.0,
        markersize=6,
        label="Total Pipeline Time (s)",
    )
    line1b = ax_a.plot(
        dx_vals,
        vox_times,
        "v--",
        color="#66bb6a",
        linewidth=1.6,
        markersize=5,
        label="Voxelization Time (s)",
    )
    ax_a.tick_params(axis="y", labelcolor="#1b5e20")
    ax_a.set_xscale("log")
    ax_a.set_ylim(0, max(total_times) * 1.35)
    ax_a.grid(True, which="both", linestyle=":", alpha=0.5)

    # Twin axis for active voxel count
    ax_a_twin = ax_a.twinx()
    ax_a_twin.set_ylabel("Active Voxel Count $N_{\\text{vox}}$", color="#0d47a1")
    line2 = ax_a_twin.plot(
        dx_vals,
        vox_counts,
        "s--",
        color="#1976d2",
        linewidth=1.8,
        markersize=5,
        label="Active Voxels ($N_{\\text{vox}}$)",
    )
    ax_a_twin.tick_params(axis="y", labelcolor="#0d47a1")
    ax_a_twin.set_yscale("log")

    # Joint legend
    lines = line1 + line1b + line2
    labels = [item.get_label() for item in lines]
    ax_a.legend(lines, labels, loc="upper center", framealpha=0.9, bbox_to_anchor=(0.5, 0.98))

    # -------------------------------------------------------------
    # Panel (b): Zero-Copy Fortran BDF Streaming Throughput
    # -------------------------------------------------------------
    ax_b = axes[0, 1]
    ax_b.set_title(
        "(b) Vectorized Fortran BDF Streaming Performance", fontweight="bold", pad=8
    )
    bdf_times = [r["bdf_write_time_ms"] for r in results_vox]
    bdf_tp = [r["bdf_throughput_m_vox_s"] for r in results_vox]

    ax_b.set_xlabel("Active Voxel Count ($N_{\\text{vox}}$)")
    ax_b.set_ylabel("BDF Export Time (ms)", color="#b71c1c")
    line3 = ax_b.plot(
        vox_counts,
        bdf_times,
        "d-",
        color="#d32f2f",
        linewidth=2.0,
        markersize=6,
        label="Export Time (ms)",
    )
    ax_b.tick_params(axis="y", labelcolor="#b71c1c")
    ax_b.grid(True, linestyle=":", alpha=0.5)

    ax_b_twin = ax_b.twinx()
    ax_b_twin.set_ylabel("Throughput ($10^6$ voxels/s)", color="#e65100")
    line4 = ax_b_twin.plot(
        vox_counts,
        bdf_tp,
        "^--",
        color="#f57c00",
        linewidth=1.8,
        markersize=6,
        label="Streaming Throughput",
    )
    ax_b_twin.tick_params(axis="y", labelcolor="#e65100")

    lines_b = line3 + line4
    labels_b = [item.get_label() for item in lines_b]
    ax_b.legend(lines_b, labels_b, loc="center right", framealpha=0.9)

    # -------------------------------------------------------------
    # Panel (c): Ground Fuel Litter Discretization Scaling (N_bins)
    # -------------------------------------------------------------
    ax_c = axes[1, 0]
    ax_c.set_title(
        "(c) 1D BFM Ground Fuel Scalability vs. $N_{\\text{bins}}$",
        fontweight="bold",
        pad=8,
    )

    m1_data = [r for r in results_litter if r["model_type"] == 1]
    m2_data = [r for r in results_litter if r["model_type"] == 2]

    bins_m1 = [r["num_bins"] for r in m1_data]
    times_m1 = [r["total_litter_ms"] for r in m1_data]
    vents_m1 = [r["vent_count"] for r in m1_data]

    bins_m2 = [r["num_bins"] for r in m2_data]
    times_m2 = [r["total_litter_ms"] for r in m2_data]
    vents_m2 = [r["vent_count"] for r in m2_data]

    ax_c.set_xlabel("Number of Discretization Bins ($N_{\\text{bins}}$)")
    ax_c.set_ylabel("BFM Generation Time (ms)", color="#37474f")
    p1 = ax_c.plot(
        bins_m1,
        times_m1,
        "o-",
        color="#455a64",
        linewidth=1.8,
        markersize=5,
        label="Model 1 Time (ms)",
    )
    p2 = ax_c.plot(
        bins_m2,
        times_m2,
        "^-",
        color="#7b1fa2",
        linewidth=1.8,
        markersize=5,
        label="Model 2 Time (ms)",
    )
    ax_c.tick_params(axis="y", labelcolor="#37474f")
    ax_c.grid(True, linestyle=":", alpha=0.5)

    ax_c_twin = ax_c.twinx()
    ax_c_twin.set_ylabel("Generated VENT Ground Patches", color="#00695c")
    p3 = ax_c_twin.plot(
        bins_m1,
        vents_m1,
        "o--",
        color="#00897b",
        alpha=0.7,
        linewidth=1.5,
        markersize=4,
        label="Model 1 VENT Patches",
    )
    p4 = ax_c_twin.plot(
        bins_m2,
        vents_m2,
        "^--",
        color="#26a69a",
        alpha=0.7,
        linewidth=1.5,
        markersize=4,
        label="Model 2 VENT Patches",
    )
    ax_c_twin.tick_params(axis="y", labelcolor="#00695c")

    lines_c = p1 + p2 + p3 + p4
    labels_c = [item.get_label() for item in lines_c]
    ax_c.legend(lines_c, labels_c, loc="center left", framealpha=0.9)

    # -------------------------------------------------------------
    # Panel (d): Stage-by-Stage Computational Budget
    # -------------------------------------------------------------
    ax_d = axes[1, 1]
    ax_d.set_title(
        "(d) Computational time Budget (Default settings, $\\Delta x = 0.20$ m)",
        fontweight="bold",
        pad=8,
    )

    clean_stage_names = {
        "Point Cloud I/O (4.95M pts)": "Point Cloud I/O (4.95M pts)",
        "3D Dynamic Voxelization (1cm -> 0.20m)": "3D Dynamic Voxelization",
        "Fortran .bdf Stream Write": "Fortran .bdf Stream Write",
        "Litter BFM Discretization & Tiling": "Litter BFM Discretization",
        "FDS Master Script Assembly": "FDS Master Script Assembly",
    }
    stages = [clean_stage_names.get(k, k) for k in budget.keys()]
    times = list(budget.values())
    total_time = sum(times)
    percentages = [(t / total_time) * 100.0 for t in times]

    colors = ["#2b5c8f", "#388e3c", "#f57c00", "#7b1fa2", "#d32f2f"]
    bars = ax_d.barh(
        stages, times, color=colors, edgecolor="black", height=0.6, alpha=0.88
    )
    ax_d.set_xlabel("Execution Time (s)")
    ax_d.tick_params(axis="y", labelsize=8.5)
    ax_d.grid(True, axis="x", linestyle=":", alpha=0.5)

    for bar, pct, t_sec in zip(bars, percentages, times):
        ax_d.text(
            bar.get_width() + total_time * 0.015,
            bar.get_y() + bar.get_height() / 2.0,
            f"{t_sec:.3f} s ({pct:.1f}%)",
            va="center",
            ha="left",
            fontsize=8.0,
            fontweight="bold",
        )

    ax_d.set_xlim(0, max(times) * 1.45)
    ax_d.invert_yaxis()

    fig.suptitle(
        "TLS_to_FDS Computational Efficiency Benchmarks (Sycan Marsh Pinus ponderosa Plot, 4.95M pts)",
        fontweight="bold",
        fontsize=12.0,
    )

    png_path = out_dir / "fig_computational_benchmarks.png"
    pdf_path = out_dir / "fig_computational_benchmarks.pdf"
    plt.savefig(png_path, dpi=300, bbox_inches="tight")
    plt.savefig(pdf_path, dpi=300, bbox_inches="tight")
    plt.close()

    # Also sync to assets/ directory if it exists
    assets_dir = Path("assets")
    if assets_dir.exists():
        import shutil

        try:
            shutil.copy2(png_path, assets_dir / "fig_computational_benchmarks.png")
            shutil.copy2(pdf_path, assets_dir / "fig_computational_benchmarks.pdf")
        except PermissionError as e:
            print(f"  [WARNING] Could not overwrite file in assets/ (file in use): {e}")

    print("\n[FIGURE CREATED] High-resolution publication plots saved to:")
    print(f"  -> PNG: {png_path}")
    print(f"  -> PDF: {pdf_path}")


# ==============================================================================
# MAIN ENTRYPOINT
# ==============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="TLS_to_FDS Computational Benchmark Suite"
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="Number of measurement repeats per condition",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/pointclouds",
        help="Path to real point cloud directory",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="benchmark_results",
        help="Destination directory for benchmark tables and figures",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick test run with fewer resolutions and bins",
    )
    parser.add_argument(
        "--plot-only",
        action="store_true",
        help="Regenerate publication figures from existing CSV benchmark tables without re-running tests",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.plot_only:
        import csv

        print(f"\n[PLOT-ONLY] Loading benchmark tables from {out_dir.resolve()}...")
        results_vox = []
        with open(out_dir / "table1_voxel_scaling.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                results_vox.append({
                    "voxel_size_m": float(row["voxel_size_m"]),
                    "active_voxels": int(row["active_voxels"]),
                    "voxelization_time_s": float(row["voxelization_time_s"]),
                    "voxelization_time_std_s": float(row["voxelization_time_std_s"]),
                    "bdf_write_time_ms": float(row["bdf_write_time_ms"]),
                    "bdf_write_time_std_ms": float(row["bdf_write_time_std_ms"]),
                    "bdf_throughput_m_vox_s": float(row["bdf_throughput_m_vox_s"]),
                    "bdf_throughput_mb_s": float(row["bdf_throughput_mb_s"]),
                    "fds_assembly_time_ms": float(row["fds_assembly_time_ms"]),
                    "total_time_s": float(row["total_time_s"]),
                    "total_time_std_s": float(row["total_time_std_s"]),
                })

        results_litter = []
        with open(out_dir / "table2_litter_scaling.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                results_litter.append({
                    "model": row["model"],
                    "model_type": int(row["model_type"]),
                    "num_bins": int(row["num_bins"]),
                    "field_time_ms": float(row["field_time_ms"]),
                    "tiling_time_ms": float(row["tiling_time_ms"]),
                    "total_litter_ms": float(row["total_litter_ms"]),
                    "vent_count": int(row["vent_count"]),
                    "fds_time_ms": float(row["fds_time_ms"]),
                    "fds_size_kb": float(row["fds_size_kb"]),
                })

        budget = {}
        with open(out_dir / "table3_runtime_budget.csv", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                budget[row["stage"]] = float(row["time_seconds"])

        generate_publication_figure(results_vox, results_litter, budget, out_dir)
        return

    print("======================================================================")
    print("           TLS_to_FDS COMPUTATIONAL BENCHMARK SUITE")
    print("======================================================================")

    # 1. Capture Environment Metadata
    meta = get_system_metadata()
    print("System Environment:")
    for k, v in meta.items():
        print(f"  * {k}: {v}")
    (out_dir / "system_environment.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )

    # 2. Ingest Real TLS Data
    print(f"\nLoading real TLS datasets from: {data_dir.resolve()}...")
    datasets, names, nominal_bds, raw_min = load_real_datasets(data_dir)
    total_pts = sum(len(d) for d in datasets)
    print(
        f"[SUCCESS] Loaded {len(datasets)} fuel strata with {total_pts:,} total real LiDAR points."
    )

    # 3. Configure Matrices
    if args.quick:
        resolutions = [0.50, 0.25, 0.15]
        bins_list = [5, 10, 25]
    else:
        resolutions = [1.00, 0.50, 0.30, 0.25, 0.20, 0.15, 0.10]
        bins_list = [2, 5, 10, 15, 20, 30, 50, 75, 100]

    # 4. Run Experiment 1: 3D Grid Scaling
    results_vox = benchmark_voxel_scaling(
        datasets=datasets,
        names=names,
        nominal_bds=nominal_bds,
        resolutions=resolutions,
        repeats=args.repeats,
        output_temp_dir=out_dir / "scratch",
    )

    # 5. Run Experiment 2: Ground Fuel BFM Scaling
    results_litter = benchmark_litter_scaling(
        datasets=datasets,
        data_dir=data_dir,
        bins_list=bins_list,
        voxel_size=0.20,
        repeats=args.repeats,
        output_temp_dir=out_dir / "scratch",
    )

    # 6. Run Experiment 3: Stage-by-Stage Budget
    print("\n--- EXPERIMENT 3: Canonical Simulation Runtime Budget ---")
    budget = benchmark_runtime_budget(
        data_dir=data_dir,
        voxel_size=0.20,
        repeats=args.repeats,
        output_temp_dir=out_dir / "scratch",
    )
    total_b = sum(budget.values())
    for stage, t_sec in budget.items():
        print(f"   * {stage:40s}: {t_sec:6.3f} s ({(t_sec / total_b) * 100.0:5.1f}%)")
    print(f"   * {'TOTAL CONVERSION TIME':40s}: {total_b:6.3f} s (100.0%)")

    # 7. Exports (CSV, LaTeX, Publication Plots)
    print(f"\nExporting benchmark artifacts to: {out_dir.resolve()}...")
    export_csv_tables(results_vox, results_litter, budget, out_dir)
    export_latex_tables(results_vox, results_litter, budget, out_dir)
    generate_publication_figure(results_vox, results_litter, budget, out_dir)

    # Clean scratch
    import shutil

    scratch_dir = out_dir / "scratch"
    if scratch_dir.exists():
        shutil.rmtree(scratch_dir, ignore_errors=True)

    print("\n======================================================================")
    print(" [COMPLETE] Benchmarks successfully finished!")
    print(f" Output files located in: {out_dir}")
    print("======================================================================")


if __name__ == "__main__":
    main()
