import pytest
import numpy as np
from tls_to_fds import fds_builder, litter_models, io_utils
from tls_to_fds.models import EnvParams, OutputParams, GroundFuels, DomainParams


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
    assert "DENSITY               = 67.0" in bp_no_embers   # ASH

    bp_embers = fds_builder.get_static_boilerplate(track_embers=True)
    assert "DENSITY               = 180.0" in bp_embers  # CHAR override Mell et al.
    assert "DENSITY               = 50.0" in bp_embers   # ASH override Mell et al.


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


def test_litter_bfm_tiles():
    litter_2d = np.array([
        [0.0, 5.0, 5.0, 12.0],
        [0.0, 5.0, 12.0, 12.0],
    ])
    bounds = (0.0, 0.0, 0.0, 4.0, 2.0, 5.0)
    sizes = (1.0, 1.0, 1.0)
    
    surfs, vents = litter_models.build_litter_bfm_tiles(
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


def test_default_config_values():
    default_dev_time = io_utils.get_default("env_params", "wind_dev_time", 15.0)
    assert default_dev_time == 25.0
