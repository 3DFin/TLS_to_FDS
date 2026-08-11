import re
import pytest
import laspy
import numpy as np
from tls_to_fds import fds_builder
from tls_to_fds.main import run_pipeline
from tls_to_fds.models import (
    OutputParams,
    RuntimeConfig,
    GroundFuels,
    EnvParams,
    DomainParams,
)


def test_ros_devc_lines_generation():
    bounds = [0.0, 0.0, 0.0, 10.0, 20.0, 5.0]

    # Test South Edge (Y-propagation)
    devc_y = fds_builder.generate_ros_devc_block(bounds, "Line: South Edge (y_min)")
    assert "RoS_Line_1" in devc_y
    assert "RoS_Line_4" in devc_y
    assert "MAXLOC Y" in devc_y
    # 20% of 10m = 2m offset (XB=2.00,2.00,0.00,20.00...)
    assert "XB=2.00,2.00,0.00,20.00" in devc_y

    # Test West Edge (X-propagation)
    devc_x = fds_builder.generate_ros_devc_block(bounds, "Line: West Edge (x_min)")
    assert "RoS_Line_1" in devc_x
    assert "RoS_Line_4" in devc_x
    assert "MAXLOC X" in devc_x
    # 20% of 20m = 4m offset (XB=0.00,10.00,4.00,4.00...)
    assert "XB=0.00,10.00,4.00,4.00" in devc_x


def test_dump_and_misc_block():
    out_params = OutputParams(
        hrrpua=True,
        flame=True,
        temp=True,
        wind=True,
        biomass=False,
        restart_active=True,
        dt_restart=50.0,
        dt_hrr=0.2,
        dt_devc=0.2,
        dt_part=0.2,
    )
    block = fds_builder.generate_dump_and_misc_block(out_params)
    assert "&DUMP DT_RESTART=50.00, DT_HRR=0.20, DT_DEVC=0.20, DT_PART=0.20 /" in block
    assert "&MISC RESTART=.FALSE. /" in block


def test_ember_material_adjustments():
    bp_no_embers = fds_builder.get_static_boilerplate(track_embers=False)
    assert "DENSITY               = 300.0" in bp_no_embers  # CHAR
    assert "DENSITY               = 67.0" in bp_no_embers  # ASH

    bp_embers = fds_builder.get_static_boilerplate(track_embers=True)
    assert "DENSITY               = 180.0" in bp_embers  # CHAR override Mell et al.
    assert "DENSITY               = 50.0" in bp_embers  # ASH override Mell et al.


def test_multi_height_slice_planes():
    bounds = [0.0, 0.0, 0.0, 10.0, 10.0, 5.0]
    fuel_layers = []
    out_params = OutputParams(
        hrrpua=True,
        flame=True,
        temp=True,
        wind=True,
        biomass=False,
        slice_heights="0.5, 1.5, 2.5",
    )
    slcf_block = fds_builder.generate_output_blocks(out_params, bounds, fuel_layers)
    assert "&SLCF PBZ=0.50, QUANTITY='TEMPERATURE'" in slcf_block
    assert "&SLCF PBZ=1.50, QUANTITY='TEMPERATURE'" in slcf_block
    assert "&SLCF PBZ=2.50, QUANTITY='TEMPERATURE'" in slcf_block
    assert "&SLCF PBZ=0.50, QUANTITY='VELOCITY'" in slcf_block


@pytest.fixture
def dummy_forest_setup(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Create dummy point cloud (10m x 20m x 8m)
    las_path = input_dir / "trees.las"
    header = laspy.LasHeader(point_format=2, version="1.2")
    las = laspy.LasData(header)

    x_vals = np.linspace(10.0, 20.0, 10)
    y_vals = np.linspace(10.0, 30.0, 10)
    z_vals = np.linspace(0.0, 8.0, 10)

    las.x = x_vals
    las.y = y_vals
    las.z = z_vals
    las.write(las_path)

    dtm_path = tmp_path / "dtm.csv"
    dtm_path.write_text("x,y,z\n10.0,10.0,0.0\n20.0,30.0,0.0\n")

    return input_dir, output_dir, dtm_path


def test_spatial_placements_audit(dummy_forest_setup):
    input_dir, output_dir, dtm_path = dummy_forest_setup

    env_params = EnvParams(
        sim_time=120.0,
        wind_dev_time=15.0,
        wind_dir=0.0,
        wind_speed=3.0,
        hrrpua=500.0,
        track_embers=False,
        ign_duration=30.0,
        obukhov=-350.0,
        z0=0.5,
        ember_density=62.5,
        ember_velocity=0.0,
        ign_pattern="Line: South Edge (y_min)",
        vent_width=2.0,
        ros_tracking=True,
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
        dispersion_sigma=1.5,
    )

    output_params = OutputParams(
        hrrpua=True,
        flame=True,
        temp=True,
        wind=True,
        biomass=True,
        slice_heights="0.5, 1.5, 3.0",
    )

    domain_params = DomainParams(
        lateral_pad=10.0, top_pad=20.0, sky_multiplier=2, mpi_x=2, mpi_y=2
    )

    config = RuntimeConfig(
        input_directory=str(input_dir),
        output_directory=str(output_dir),
        output_filename="audit_sim",
        preset_name="ponderosa_pine_summer",
        voxel_size=1.0,
        fuel_layers=[
            {
                "filename": "trees.las",
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

    fds_file = output_dir / "audit_sim.fds"
    assert fds_file.exists()
    fds = fds_file.read_text()

    # 1. Audit Open Mesh Boundary Vents
    assert "&VENT MB='XMIN', SURF_ID='OPEN' /" in fds
    assert "&VENT MB='XMAX', SURF_ID='OPEN' /" in fds
    assert "&VENT MB='YMIN', SURF_ID='OPEN' /" in fds
    assert "&VENT MB='YMAX', SURF_ID='OPEN' /" in fds
    assert "&VENT MB='ZMAX', SURF_ID='OPEN' /" in fds

    # 2. Audit Ignition Vent (South Edge: y_min=0.0 to 2.0, x=0.0 to 11.0)
    ign_match = re.search(
        r"&VENT XB=([\d\.\-]+),([\d\.\-]+),([\d\.\-]+),([\d\.\-]+),([\d\.\-]+),([\d\.\-]+), SURF_ID='IGN FIRE'",
        fds,
    )
    assert ign_match is not None
    x1, x2, y1, y2, z1, z2 = [float(val) for val in ign_match.groups()]
    assert (x1, x2) == (0.0, 11.0)
    assert (y1, y2) == (0.0, 2.0)
    assert (z1, z2) == (0.0, 0.0)

    # 3. Audit Litter VENT Placement (Bounded in forest domain [0..11] X and [0..21] Y)
    litter_vents = re.findall(
        r"&VENT XB=([\d\.\-]+),([\d\.\-]+),([\d\.\-]+),([\d\.\-]+),[\d\.\-]+,[\d\.\-]+, SURF_ID='Litter_Class_\d+'",
        fds,
    )
    assert len(litter_vents) > 0
    for lx1, lx2, ly1, ly2 in litter_vents:
        assert float(lx1) >= 0.0
        assert float(lx2) <= 11.0
        assert float(ly1) >= 0.0
        assert float(ly2) <= 21.0

    # 4. Audit SLCF Slice Heights (0.5, 1.5, 3.0 m)
    assert "&SLCF PBZ=0.50, QUANTITY='TEMPERATURE'" in fds
    assert "&SLCF PBZ=1.50, QUANTITY='TEMPERATURE'" in fds
    assert "&SLCF PBZ=3.00, QUANTITY='TEMPERATURE'" in fds
    assert "&SLCF PBZ=0.50, QUANTITY='HRRPUV'" in fds
    assert "&SLCF PBZ=1.50, QUANTITY='HRRPUV'" in fds
    assert "&SLCF PBZ=3.00, QUANTITY='HRRPUV'" in fds

    # 5. Audit Y-center Slice (Forest Y is 0..21, Y-center is 10.5)
    assert "&SLCF PBY=10.50, QUANTITY='TEMPERATURE'" in fds
    assert "&SLCF PBY=10.50, QUANTITY='HRRPUV'" in fds

    # 6. Audit RoS Trackers (4 lines parallel to Y, at 20%, 40%, 60%, 80% X offsets)
    assert "XB=2.20,2.20,0.00,21.00,0.00,9.00" in fds
    assert "XB=4.40,4.40,0.00,21.00,0.00,9.00" in fds
    assert "XB=6.60,6.60,0.00,21.00,0.00,9.00" in fds
    assert "XB=8.80,8.80,0.00,21.00,0.00,9.00" in fds
