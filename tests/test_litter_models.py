import numpy as np
import pytest

from tls_to_fds.litter_models import (
    CanopyTurnoverLitterModel,
    TreeDistanceLitterModel,
    load_tree_map,
)


def test_load_tree_map_csv(tmp_path):
    csv_file = tmp_path / "treemap.csv"
    csv_file.write_text("x,y,z\n10.5,20.2,1.5\n30.0,40.0,2.0\n")

    stems = load_tree_map(csv_file)
    assert stems.shape == (2, 2)
    np.testing.assert_allclose(stems[0], [10.5, 20.2])
    np.testing.assert_allclose(stems[1], [30.0, 40.0])


def test_load_tree_map_semicolon_no_header(tmp_path):
    csv_file = tmp_path / "treemap_3dfin.csv"
    # Write with UTF-8 BOM (\ufeff)
    csv_file.write_text(
        "\ufeff-4.459;-1.022;2\n-1.825;-5.1015;2.0005\n", encoding="utf-8"
    )

    stems = load_tree_map(csv_file)
    assert stems.shape == (2, 2)
    np.testing.assert_allclose(stems[0], [-4.459, -1.022])
    np.testing.assert_allclose(stems[1], [-1.825, -5.1015])


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
    model = TreeDistanceLitterModel(
        tree_stems=stems,
        base_bulk_density=15.0,
        min_bulk_density=3.5,
    )
    bd_grid = model.compute_litter_distribution((0, 0, 10, 10), (1, 1))

    assert bd_grid.shape == (10, 10)
    # Empty tree stems defaults to baseline dry bulk density (base_bulk_density)
    np.testing.assert_allclose(bd_grid, 15.0)


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

    # Test with decomposition_rate=0.0 to verify backward-compatible mass conservation
    model = CanopyTurnoverLitterModel(
        turnover_rate=0.25,
        accumulation_time=4.0,
        dispersion_sigma=2.0,
        decomposition_rate=0.0,
        consumption_rate=1.0,
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
    # annual deposition L = 3.75 * 0.25 = 0.9375 kg/m2/yr
    # direct drop = 0.9375 * 4.0 = 3.75 kg/m2
    # total grid mass = 3.75 * 100 cells = 375.0 kg
    expected_total_mass = 375.0
    actual_total_mass = float(np.sum(litter_load))

    assert actual_total_mass == pytest.approx(expected_total_mass, rel=1e-3)


def test_canopy_turnover_olson_decomposition():
    """Verifies that Olson decomposition decay matches Eq. (4) of Sánchez-López et al. (2026)."""
    voxel_counts = np.ones((4, 10, 10), dtype=float) * 50
    voxel_sizes = (1.0, 1.0, 1.0)  # dx, dy, dz

    k = 0.20  # yr-1
    t = 3.0  # years
    turnover = 0.20

    model = CanopyTurnoverLitterModel(
        turnover_rate=turnover,
        accumulation_time=t,
        dispersion_sigma=0.0,  # no dispersion for direct comparison
        decomposition_rate=k,
        consumption_rate=1.0,
    )

    litter_load = model.compute_litter_distribution(
        voxel_point_counts=voxel_counts,
        voxel_sizes=voxel_sizes,
        nominal_canopy_bd=1.0,
    )

    # CFL = 4 layers * 1.0 kg/m3 * 1.0 m = 4.0 kg/m2
    # L = 4.0 * 0.20 = 0.80 kg/m2/yr
    # B(t) = (L / k) * (1 - exp(-k * t)) = (0.80 / 0.20) * (1 - exp(-0.60)) = 4.0 * (1 - 0.5488116) = 1.80475 kg/m2
    expected_load = (0.80 / k) * (1.0 - np.exp(-k * t))
    np.testing.assert_allclose(litter_load, expected_load, rtol=1e-4)


def test_canopy_turnover_partial_fire_consumption():
    """Verifies that partial fire consumption (C < 1.0) includes steady-state residual carryover."""
    voxel_counts = np.ones((4, 5, 5), dtype=float) * 50
    voxel_sizes = (1.0, 1.0, 1.0)

    k = 0.15  # yr-1
    t = 2.0  # years (FRI)
    turnover = 0.22  # from paper Table 4
    c = 0.65  # 65% consumption (35% residual carryover)

    model = CanopyTurnoverLitterModel(
        turnover_rate=turnover,
        accumulation_time=t,
        dispersion_sigma=0.0,
        decomposition_rate=k,
        consumption_rate=c,
    )

    litter_load = model.compute_litter_distribution(
        voxel_point_counts=voxel_counts,
        voxel_sizes=voxel_sizes,
        nominal_canopy_bd=1.0,
    )

    # CFL = 4.0 kg/m2, L = 4.0 * 0.22 = 0.88 kg/m2/yr
    # decay = exp(-0.15 * 2) = exp(-0.30)
    # accum_factor = (1 - exp(-0.30)) / 0.15
    # b_ss_factor = accum_factor / (1 - (1 - 0.65) * exp(-0.30))
    # expected = L * b_ss_factor
    decay = np.exp(-k * t)
    accum_factor = (1.0 - decay) / k
    b_ss_factor = accum_factor / (1.0 - (1.0 - c) * decay)
    expected_load = 0.88 * b_ss_factor

    np.testing.assert_allclose(litter_load, expected_load, rtol=1e-4)


def test_load_dtm_and_build_bdf(tmp_path):
    from tls_to_fds.litter_models import build_litter_bdf_voxels, load_dtm

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


def test_litter_bfm_tiles_2d_coalescing():
    from tls_to_fds.litter_models import build_litter_bfm_tiles

    # 2 rows with identical horizontal spans:
    # row 0: class 1 (cols 1..2), class 10 (col 3)
    # row 1: class 1 (cols 1..2), class 10 (col 3)
    litter_2d = np.array(
        [
            [0.0, 5.0, 5.0, 12.0],
            [0.0, 5.0, 5.0, 12.0],
        ]
    )
    bounds = (0.0, 0.0, 0.0, 4.0, 2.0, 5.0)
    sizes = (1.0, 1.0, 1.0)

    # 1D merging produces 4 vents (2 per row)
    _, vents_1d = build_litter_bfm_tiles(
        litter_2d=litter_2d,
        domain_bounds=bounds,
        voxel_sizes=sizes,
        merge_2d=False,
    )
    assert len(vents_1d) == 4

    # 2D coalescing merges identical vertical spans into 2 vents
    _, vents_2d = build_litter_bfm_tiles(
        litter_2d=litter_2d,
        domain_bounds=bounds,
        voxel_sizes=sizes,
        merge_2d=True,
    )
    assert len(vents_2d) == 2

    # Verify that the total area covered by 1D and 2D vents is identical
    area_1d = sum((v["xb"][1] - v["xb"][0]) * (v["xb"][3] - v["xb"][2]) for v in vents_1d)
    area_2d = sum((v["xb"][1] - v["xb"][0]) * (v["xb"][3] - v["xb"][2]) for v in vents_2d)
    assert area_1d == pytest.approx(area_2d)
    assert area_2d == pytest.approx(6.0)  # 2 + 1 + 2 + 1 = 6 m2


def test_export_litter_rasters(tmp_path):
    from tls_to_fds.litter_models import export_litter_rasters

    litter_2d = np.array(
        [
            [10.0, 15.0, 20.0],
            [12.0, 18.0, 25.0],
        ]
    )
    bounds = (0.0, 0.0, 0.0, 3.0, 2.0, 5.0)

    out_files = export_litter_rasters(
        litter_2d=litter_2d,
        litter_depth=0.05,
        domain_bounds=bounds,
        voxel_size=1.0,
        output_dir=tmp_path,
        prefix="litter",
        tree_stems=np.array([[1.5, 0.5]]),
    )

    assert out_files["csv_bd"].exists()
    assert out_files["tif_bd"].exists()
    assert out_files["png_bd"].exists()
    assert out_files["csv_load"].exists()
    assert out_files["tif_load"].exists()
    assert out_files["png_load"].exists()

    # Verify CSV file contents
    csv_bd = np.loadtxt(out_files["csv_bd"], delimiter=",")
    assert csv_bd.shape == (2, 3)
    np.testing.assert_allclose(csv_bd[0], [10.0, 15.0, 20.0])

    csv_load = np.loadtxt(out_files["csv_load"], delimiter=",")
    assert csv_load.shape == (2, 3)
    np.testing.assert_allclose(csv_load[0], [0.5, 0.75, 1.0])
