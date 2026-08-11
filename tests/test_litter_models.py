import pytest
import numpy as np
from tls_to_fds.litter_models import (
    load_tree_map,
    TreeDistanceLitterModel,
    CanopyTurnoverLitterModel,
)


def test_load_tree_map_csv(tmp_path):
    csv_file = tmp_path / "treemap.csv"
    csv_file.write_text("x,y,z\n10.5,20.2,1.5\n30.0,40.0,2.0\n")

    stems = load_tree_map(csv_file)
    assert stems.shape == (2, 2)
    np.testing.assert_allclose(stems[0], [10.5, 20.2])
    np.testing.assert_allclose(stems[1], [30.0, 40.0])


def test_tree_distance_model_decay():
    stems = np.array([[10.0, 10.0]])
    model = TreeDistanceLitterModel(
        tree_stems=stems,
        base_bulk_density=20.0,
        min_bulk_density=2.0,
        alpha=0.5,
    )

    grid_bounds = (0.0, 0.0, 20.0, 20.0)
    resolution = (1.0, 1.0)
    bd_grid = model.compute_litter_distribution(grid_bounds, resolution)

    assert bd_grid.shape == (20, 20)

    # Check that density near tree (x=10, y=10) is significantly higher than far corner (x=0, y=0)
    near_tree_val = bd_grid[10, 10]
    far_val = bd_grid[0, 0]

    assert near_tree_val > far_val
    assert near_tree_val > 10.0
    assert far_val >= 2.0


def test_tree_distance_empty_stems():
    stems = np.array([])
    model = TreeDistanceLitterModel(tree_stems=stems, min_bulk_density=3.5)
    bd_grid = model.compute_litter_distribution((0, 0, 10, 10), (1, 1))

    assert bd_grid.shape == (10, 10)
    np.testing.assert_allclose(bd_grid, 3.5)


def test_point_density_correction():
    counts = np.array(
        [
            [[10, 20], [30, 0]],
            [[0, 40], [10, 10]],
        ]
    )  # Mean of non-zero (10, 20, 30, 40, 10, 10) = 120 / 6 = 20
    nominal_bd = 2.0

    corrected = CanopyTurnoverLitterModel.apply_point_density_correction(
        counts, nominal_bd
    )

    # For count = 20, corrected should equal nominal_bd (2.0)
    assert corrected[0, 0, 1] == pytest.approx(2.0)
    # For count = 10, corrected should equal half (1.0)
    assert corrected[0, 0, 0] == pytest.approx(1.0)
    # For count = 40, corrected should equal double (4.0)
    assert corrected[1, 0, 1] == pytest.approx(4.0)
    # Zero counts remain zero
    assert corrected[0, 1, 1] == 0.0


def test_canopy_turnover_mass_conservation():
    voxel_counts = np.ones((5, 10, 10), dtype=float) * 50
    voxel_sizes = (1.0, 1.0, 0.5)  # dx, dy, dz

    model = CanopyTurnoverLitterModel(
        turnover_rate=0.25,
        accumulation_time=4.0,
        dispersion_sigma=2.0,
    )

    litter_load = model.compute_litter_distribution(
        voxel_point_counts=voxel_counts,
        voxel_sizes=voxel_sizes,
        nominal_canopy_bd=1.5,
    )

    assert litter_load.shape == (10, 10)

    # Compute expected direct load without dispersion
    # corrected BD = 1.5 everywhere
    # CFL = 5 layers * 1.5 kg/m3 * 0.5 m = 3.75 kg/m2
    # direct drop = 3.75 * 0.25 * 4.0 = 3.75 kg/m2
    # total grid mass = 3.75 * 100 cells = 375.0 kg
    expected_total_mass = 375.0
    actual_total_mass = float(np.sum(litter_load))

    assert actual_total_mass == pytest.approx(expected_total_mass, rel=1e-3)


def test_load_dtm_and_build_bdf(tmp_path):
    from tls_to_fds.litter_models import load_dtm, build_litter_bdf_voxels

    dtm_file = tmp_path / "dtm.csv"
    dtm_file.write_text("x,y,z\n5.0,5.0,2.0\n15.0,15.0,3.0\n")

    dtm_pts = load_dtm(dtm_file)
    assert dtm_pts.shape == (2, 3)

    litter_2d = np.ones((20, 20), dtype=float) * 15.0  # 15 kg/m3
    domain_bounds = (
        0.0,
        0.0,
        0.0,
        20.0,
        20.0,
        10.0,
    )  # (xmin, ymin, zmin, xmax, ymax, zmax)
    voxel_sizes = (1.0, 1.0, 1.0)

    v_grid = build_litter_bdf_voxels(
        litter_2d_density=litter_2d,
        domain_bounds=domain_bounds,
        voxel_sizes=voxel_sizes,
        litter_depth=0.05,
        dtm_points=dtm_pts,
    )

    assert v_grid.shape == (10, 20, 20)
    # Check that at grid cell (y=5, x=5), voxel k=2 (z=2.0) has density 15.0
    assert v_grid[2, 5, 5] == 15.0


def test_load_dtm_obj(tmp_path):
    from tls_to_fds.litter_models import load_dtm

    obj_file = tmp_path / "dtm.obj"
    obj_file.write_text(
        "# CloudCompare DTM Mesh Export\nv 1.0 2.0 3.0\nv 4.0 5.0 6.0\nf 1 2 3\n"
    )

    pts = load_dtm(obj_file)
    assert pts.shape == (2, 3)
    np.testing.assert_allclose(pts[0], [1.0, 2.0, 3.0])
    np.testing.assert_allclose(pts[1], [4.0, 5.0, 6.0])


def test_litter_bfm_tiles():
    from tls_to_fds.litter_models import build_litter_bfm_tiles

    litter_2d = np.array(
        [
            [0.0, 5.0, 5.0, 12.0],
            [0.0, 5.0, 12.0, 12.0],
        ]
    )
    bounds = (0.0, 0.0, 0.0, 4.0, 2.0, 5.0)
    sizes = (1.0, 1.0, 1.0)

    surfs, vents = build_litter_bfm_tiles(
        litter_2d=litter_2d,
        domain_bounds=bounds,
        voxel_sizes=sizes,
        litter_depth=0.045,
        litter_moisture=0.12,
        sv_ratio=4800.0,
        num_bins=5,
    )

    assert len(surfs) > 0
    assert len(vents) > 0
    assert surfs[0]["surf_id"] == "Litter_Class_1"
    # Row 0 has 2 consecutive cells with value 5.0 (columns 1 and 2), which should be merged
    merged_vents = [v for v in vents if v["xb"][0] == 1.0 and v["xb"][1] == 3.0]
    assert len(merged_vents) == 1
