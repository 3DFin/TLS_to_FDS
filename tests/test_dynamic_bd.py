import numpy as np
import pytest
from pathlib import Path

from tls_to_fds import io_utils, spatial_utils


def test_2stage_micro_voxelization_duplicate_elimination():
    # 50 duplicate points at (1.0, 1.0, 1.0) and 1 point at (2.0, 2.0, 2.0)
    dup_pts = np.tile([1.0, 1.0, 1.0], (50, 1))
    single_pt = np.array([[2.0, 2.0, 2.0]])
    raw_points = np.vstack([dup_pts, single_pt])

    voxel_size = 0.5
    nominal_bd = 1.0

    sim_coords, bd_array, stats = spatial_utils.compute_dynamic_voxel_bulk_densities(
        raw_points=raw_points,
        voxel_size=voxel_size,
        nominal_bd=nominal_bd,
        sub_voxel_size=0.01,
    )

    # 1cm micro-voxelization collapses the 50 duplicate points to 1 micro-voxel center
    # Therefore, both simulation voxels have P_v = 1 micro-voxel
    assert len(sim_coords) == 2
    assert bd_array[0] == pytest.approx(bd_array[1])
    assert bd_array[0] == pytest.approx(nominal_bd)


def test_dynamic_bd_mass_preservation():
    np.random.seed(42)
    # Create 500 points in region A and 100 points in region B
    pts_a = np.random.uniform(0.0, 1.0, (500, 3))
    pts_b = np.random.uniform(2.0, 3.0, (100, 3))
    raw_points = np.vstack([pts_a, pts_b])

    voxel_size = 0.2
    nominal_bd = 1.5

    sim_coords, bd_array, stats = spatial_utils.compute_dynamic_voxel_bulk_densities(
        raw_points=raw_points,
        voxel_size=voxel_size,
        nominal_bd=nominal_bd,
        sub_voxel_size=0.01,
    )

    n_voxels = len(sim_coords)
    expected_total_mass = n_voxels * nominal_bd
    actual_total_mass = float(np.sum(bd_array))

    assert actual_total_mass == pytest.approx(expected_total_mass, rel=1e-5)
    assert stats["max_bd"] > stats["min_bd"]


def test_dynamic_bd_clamping_bounds():
    np.random.seed(42)
    pts_dense = np.random.uniform(0.0, 0.2, (2000, 3))
    pts_sparse = np.random.uniform(2.0, 2.2, (10, 3))
    raw_points = np.vstack([pts_dense, pts_sparse])

    voxel_size = 0.2
    nominal_bd = 2.0
    min_factor = 0.1
    max_factor = 2.0

    sim_coords, bd_array, stats = spatial_utils.compute_dynamic_voxel_bulk_densities(
        raw_points=raw_points,
        voxel_size=voxel_size,
        nominal_bd=nominal_bd,
        sub_voxel_size=0.01,
        min_factor=min_factor,
        max_factor=max_factor,
    )

    # Check bounds relative to nominal_bd * mass_ratio
    mass_ratio = stats["total_mass_ratio"]
    assert np.min(bd_array) >= (nominal_bd * min_factor * mass_ratio) - 1e-6
    assert np.max(bd_array) <= (nominal_bd * max_factor * mass_ratio) + 1e-6


def test_fortran_export_with_bd_array(tmp_path):
    sim_coords = np.array(
        [
            [0.1, 0.1, 0.1],
            [0.3, 0.3, 0.3],
            [0.5, 0.5, 0.5],
        ]
    )
    bd_array = np.array([0.5, 1.2, 2.1])
    voxel_size = 0.2

    io_utils.generate_fortran(
        name="test_dynamic",
        array_2d=sim_coords,
        voxel_size=voxel_size,
        bd=bd_array,
        output_dir=tmp_path,
    )

    bdf_path = tmp_path / "test_dynamic.bdf"
    assert bdf_path.exists()
    assert bdf_path.stat().st_size > 0


def test_pipeline_run_with_dynamic_bd(tmp_path):
    import laspy
    from tls_to_fds.main import run_pipeline

    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    las_path = input_dir / "canopy.las"
    header = laspy.LasHeader(point_format=3, version="1.2")
    las = laspy.LasData(header)
    np.random.seed(123)
    las.x = np.random.uniform(0.0, 5.0, 100)
    las.y = np.random.uniform(0.0, 5.0, 100)
    las.z = np.random.uniform(0.0, 5.0, 100)
    las.write(las_path)

    config = {
        "input_directory": str(input_dir),
        "output_directory": str(output_dir),
        "output_filename": "test_dyn_sim",
        "preset_name": "ponderosa_pine_summer",
        "voxel_size": 1.0,
        "fuel_layers": [
            {
                "filename": "canopy.las",
                "semantic_class": "Surface Fuel",
                "bulk_density": 0.8,
                "dynamic_bd": True,
            }
        ],
    }

    run_pipeline(config)

    bdf_file = output_dir / "canopy.bdf"
    fds_file = output_dir / "test_dyn_sim.fds"
    assert bdf_file.exists()
    assert fds_file.exists()
