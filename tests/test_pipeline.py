import re

import laspy
import numpy as np
import pytest

from tls_to_fds.main import run_pipeline
from tls_to_fds.models import (
    DomainParams,
    EnvParams,
    GroundFuels,
    OutputParams,
    RuntimeConfig,
)


@pytest.fixture
def sample_las_and_tree_map(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Create dummy LAS file
    las_path = input_dir / "canopy.las"
    header = laspy.LasHeader(point_format=2, version="1.2")
    las = laspy.LasData(header)
    las.x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    las.y = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    las.z = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    las.write(las_path)

    # Create dummy tree map
    tree_map_path = tmp_path / "tree_map.csv"
    tree_map_path.write_text("x,y,z\n2.5,2.5,0.0\n")

    # Create dummy DTM
    dtm_path = tmp_path / "dtm.csv"
    dtm_path.write_text("x,y,z\n0.0,0.0,0.0\n5.0,5.0,0.5\n")

    return input_dir, output_dir, tree_map_path, dtm_path


def test_pipeline_model_1_tree_distance(sample_las_and_tree_map):
    input_dir, output_dir, tree_map_path, dtm_path = sample_las_and_tree_map

    env_params = EnvParams(
        sim_time=100.0,
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
    )

    ground_fuels = GroundFuels(
        litter_active=True,
        litter_depth=0.05,
        litter_bd=15.0,
        litter_moisture=0.1,
        litter_model_mode="Model 1: Tree Distance",
        tree_map_path=str(tree_map_path),
        dtm_path=str(dtm_path),
        decay_alpha=0.5,
        min_litter_bd=2.0,
    )

    output_params = OutputParams(
        hrrpua=True, flame=True, temp=True, wind=True, biomass=True
    )
    domain_params = DomainParams(
        lateral_pad=2.0, top_pad=5.0, sky_multiplier=2, mpi_x=1, mpi_y=1
    )

    config = RuntimeConfig(
        input_directory=str(input_dir),
        output_directory=str(output_dir),
        output_filename="test_m1",
        preset_name="ponderosa_pine_summer",
        voxel_size=1.0,
        fuel_layers=[
            {
                "filename": "canopy.las",
                "semantic_class": "Surface Fuel",
                "bulk_density": 1.5,
                "moisture_fraction": 0.1,
                "sv_ratio": 3588.0,
                "length": 0.10,
                "drag": 2.8,
            }
        ],
        env_params=env_params,
        ground_fuels=ground_fuels,
        output_params=output_params,
        domain_params=domain_params,
    )

    run_pipeline(config)

    assert (output_dir / "test_m1.fds").exists()
    fds_content = (output_dir / "test_m1.fds").read_text()
    assert "Litter_Class_" in fds_content
    assert "DYNAMIC GROUND LITTER LAYER" in fds_content


def test_pipeline_model_2_canopy_turnover(sample_las_and_tree_map):
    input_dir, output_dir, _tree_map_path, dtm_path = sample_las_and_tree_map

    env_params = EnvParams(
        sim_time=100.0,
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
    )

    ground_fuels = GroundFuels(
        litter_active=True,
        litter_depth=0.05,
        litter_bd=15.0,
        litter_moisture=0.1,
        litter_model_mode="Model 2: Canopy Turnover",
        dtm_path=str(dtm_path),
        turnover_rate=0.20,
        accumulation_years=3.0,
        dispersion_sigma=1.0,
    )

    output_params = OutputParams(
        hrrpua=True, flame=True, temp=True, wind=True, biomass=True
    )
    domain_params = DomainParams(
        lateral_pad=2.0, top_pad=5.0, sky_multiplier=2, mpi_x=1, mpi_y=1
    )

    config = RuntimeConfig(
        input_directory=str(input_dir),
        output_directory=str(output_dir),
        output_filename="test_m2",
        preset_name="ponderosa_pine_summer",
        voxel_size=1.0,
        fuel_layers=[
            {
                "filename": "canopy.las",
                "semantic_class": "Surface Fuel",
                "bulk_density": 1.5,
                "moisture_fraction": 0.1,
                "sv_ratio": 3588.0,
                "length": 0.10,
                "drag": 2.8,
            }
        ],
        env_params=env_params,
        ground_fuels=ground_fuels,
        output_params=output_params,
        domain_params=domain_params,
    )

    run_pipeline(config)

    assert (output_dir / "test_m2.fds").exists()
    fds_content = (output_dir / "test_m2.fds").read_text()
    assert "Litter_Class_" in fds_content
    assert "DYNAMIC GROUND LITTER LAYER" in fds_content

    # Verify that all Litter VENT tiles are strictly within forest_bounds [0.0, 5.0] and not lateral padding [-2.0, 6.0]
    vent_matches = re.findall(
        r"&VENT XB=([\d\.\-]+),([\d\.\-]+),([\d\.\-]+),([\d\.\-]+),[\d\.\-]+,[\d\.\-]+, SURF_ID='Litter_Class_\d+'",
        fds_content,
    )
    assert len(vent_matches) > 0
    for x1, x2, y1, y2 in vent_matches:
        assert float(x1) >= 0.0
        assert float(x2) <= 5.0
        assert float(y1) >= 0.0
        assert float(y2) <= 5.0
