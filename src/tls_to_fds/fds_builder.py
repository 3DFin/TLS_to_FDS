import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Union
from .io_utils import safe_get, get_default

def generate_mesh_block(base_bounds: List[float], sky_bounds: List[float], 
                        nx: int, ny: int, nz: int, 
                        domain_params: Any, base_voxel: float) -> str:
    assert len(base_bounds) == 6, f"Error: Expected 6 boundary coordinates, got {len(base_bounds)}"
    assert nx > 0 and ny > 0 and nz > 0, "Error: Mesh cell counts must be greater than zero."

    mpi_x = safe_get(domain_params, 'mpi_x', get_default('domain_params', 'mpi_x', 2))
    mpi_y = safe_get(domain_params, 'mpi_y', get_default('domain_params', 'mpi_y', 3))
    sky_mult = safe_get(domain_params, 'sky_multiplier', get_default('domain_params', 'sky_multiplier', 2))
    top_pad = safe_get(domain_params, 'top_pad', get_default('domain_params', 'top_pad', 20.0))

    x_min, y_min, z_min, x_max, y_max, z_max = base_bounds
    nx_per_mesh = nx // mpi_x
    ny_per_mesh = ny // mpi_y
    
    dx = (x_max - x_min) / mpi_x
    dy = (y_max - y_min) / mpi_y
    
    block = "!! FDS DOMAIN CONFIGURATION\n"
    mesh_idx = 1

    for i in range(mpi_x):
        for j in range(mpi_y):
            xb_min = x_min + (i * dx)
            xb_max = x_min + ((i + 1) * dx)
            yb_min = y_min + (j * dy)
            yb_max = y_min + ((j + 1) * dy)
            block += f"&MESH ID='Base_{mesh_idx}', IJK={nx_per_mesh},{ny_per_mesh},{nz}, XB={xb_min:.2f},{xb_max:.2f},{yb_min:.2f},{yb_max:.2f},{z_min:.2f},{z_max:.2f} /\n"
            mesh_idx += 1
          
    if top_pad > 0:
        sx_min, sy_min, sz_min, sx_max, sy_max, sz_max = sky_bounds
        sky_voxel = base_voxel * sky_mult
        snx = int(round((sx_max - sx_min) / sky_voxel))
        sny = int(round((sy_max - sy_min) / sky_voxel))
        snz = int(round((sz_max - sz_min) / sky_voxel))
        block += f"&MESH ID='Sky_1', IJK={snx},{sny},{snz}, XB={sx_min:.2f},{sx_max:.2f},{sy_min:.2f},{sy_max:.2f},{sz_min:.2f},{sz_max:.2f} /\n"
        
    block += "\n"
    
    for vent in ['XMIN', 'XMAX', 'YMIN', 'YMAX', 'ZMAX']:
        block += f"&VENT MB='{vent}', SURF_ID='OPEN' /\n"
        
    return block + "\n"

def generate_fuel_block(layer_config: Dict[str, Any], active_preset: Dict[str, Any], env_params: Any) -> str:
    name = layer_config['filename'].replace('.las', '').replace('.txt', '').replace('.laz', '')
    semantic_class = layer_config.get('semantic_class', 'Canopy')
    bdf_filename = f"{name}.bdf"

    moisture = layer_config.get('moisture_fraction', 0.15)
    sv_ratio = layer_config.get('sv_ratio', 3588.0)
    length = layer_config.get('length', 0.10)
    drag = layer_config.get('drag', 2.8)
    
    props = active_preset.get(semantic_class)
    if not props:
        raise ValueError(f"Fuel class '{semantic_class}' not found in the active preset.")
    
    track_embers = safe_get(env_params, 'track_embers', get_default('env_params', 'track_embers', False))
    track_str = "T" if track_embers else "F"
    ember_density = safe_get(env_params, 'ember_density', get_default('env_params', 'ember_density', 62.5))
    ember_velocity = safe_get(env_params, 'ember_velocity', get_default('env_params', 'ember_velocity', 0.0))
    
    block = f"""! --- {semantic_class.upper()}: {name} ---
&SURF ID                      = '{name} surface'
      MATL_ID(1,1)            = 'GENERIC VEGETATION'
      MATL_MASS_FRACTION(1,1) = 1.0
      MOISTURE_FRACTION       = {moisture}
      SURFACE_VOLUME_RATIO    = {sv_ratio}
      LENGTH                  = {length}
      GEOMETRY                = 'CYLINDRICAL' /

&PART ID='{name}', DRAG_COEFFICIENT={drag}, SAMPLING_FACTOR=1, SURF_ID='{name} surface'
      QUANTITIES='PARTICLE TEMPERATURE','PARTICLE BULK DENSITY', STATIC=.TRUE., COLOR='{props['color']}',
      EMBER_PARTICLE = {props['ember_particle']}, EMBER_DENSITY_THRESHOLD={ember_density}, EMBER_VELOCITY_THRESHOLD={ember_velocity}, TRACK_EMBERS={track_str} /

&INIT PART_ID='{name}', CELL_CENTERED=.FALSE., BULK_DENSITY_FILE='{bdf_filename}' /
"""
    return block

def get_static_boilerplate() -> str:
    return """
!! STATIC MATERIALS AND REACTIONS
&REAC FUEL='FUEL VAPOR', C=2.10, H=6.20, O=2.16, SOOT_YIELD=0.01, HEAT_OF_COMBUSTION=17425., IDEAL=T /
&SPEC ID='FUEL VAPOR', FORMULA='C2.10H6.20O2.16' /
&SPEC ID='WATER VAPOR' /

&MATL ID                    = 'GENERIC VEGETATION'
      DENSITY               = 500.
      CONDUCTIVITY          = 0.2
      SPECIFIC_HEAT_RAMP    = 'c_v'
      A                     = 1040.
      E                     = 61041.
      NU_SPEC               = 0.75
      SPEC_ID               = 'FUEL VAPOR'
      NU_MATL               = 0.25
      MATL_ID               = 'CHAR'
      HEAT_OF_REACTION      = 418. /

&MATL ID                    = 'CHAR'
      DENSITY               = 300.
      CONDUCTIVITY          = 0.052
      SPECIFIC_HEAT_RAMP    = 'c_v'
      SURFACE_OXIDATION_MODEL = T
      A                     = 465.
      E                     = 68000.
      SPEC_ID               = 'PRODUCTS','AIR'
      NU_SPEC               = 8.13,-7.17
      MATL_ID               = 'ASH'
      NU_MATL               = 0.04
      HEAT_OF_REACTION      = -25000. /

&MATL ID                    = 'ASH'
      DENSITY               = 67.
      CONDUCTIVITY          = 0.1
      SPECIFIC_HEAT_RAMP    = 'c_v' /

&MATL ID                    = 'SOIL'
      DENSITY               = 1500.
      CONDUCTIVITY          = 0.2
      SPECIFIC_HEAT         = 2.0 /

&RAMP ID='c_v', T=  0., F=1.1 /
&RAMP ID='c_v', T=200., F=2.0 /
&RAMP ID='c_v', T=800., F=2.0 /

&TAIL /
"""

def generate_bfm_surf(ground_fuels: Any, active_preset: Dict[str, Any]) -> str:
    litter_active = safe_get(ground_fuels, 'litter_active', get_default('ground_fuels', 'litter_active', False))
    duff_active = safe_get(ground_fuels, 'duff_active', get_default('ground_fuels', 'duff_active', False))
    
    if not litter_active and not duff_active:
        return ""

    matl_idx = 1
    matls, moistures, sv_ratios, mass_per_vols, thicknesses = [], [], [], [], []

    if litter_active:
        props = active_preset.get("Litter", {})
        matls.append(f"MATL_ID({matl_idx},1) = 'GENERIC VEGETATION'")
        moistures.append(f"MOISTURE_FRACTION({matl_idx}) = {safe_get(ground_fuels, 'litter_moisture', get_default('ground_fuels', 'litter_moisture', 0.1))}")
        sv_ratios.append(f"SURFACE_VOLUME_RATIO({matl_idx}) = {props.get('sv_ratio', 6000.0)}")
        mass_per_vols.append(f"MASS_PER_VOLUME({matl_idx}) = {safe_get(ground_fuels, 'litter_bd', get_default('ground_fuels', 'litter_bd', 15.0))}")
        thicknesses.append(str(safe_get(ground_fuels, 'litter_depth', get_default('ground_fuels', 'litter_depth', 0.05))))
        matl_idx += 1

    if duff_active:
        props = active_preset.get("Duff", {})
        matls.append(f"MATL_ID({matl_idx},1) = 'GENERIC VEGETATION'")
        moistures.append(f"MOISTURE_FRACTION({matl_idx}) = {safe_get(ground_fuels, 'duff_moisture', get_default('ground_fuels', 'duff_moisture', 0.15))}")
        sv_ratios.append(f"SURFACE_VOLUME_RATIO({matl_idx}) = {props.get('sv_ratio', 8000.0)}")
        mass_per_vols.append(f"MASS_PER_VOLUME({matl_idx}) = {safe_get(ground_fuels, 'duff_bd', get_default('ground_fuels', 'duff_bd', 30.0))}")
        thicknesses.append(str(safe_get(ground_fuels, 'duff_depth', get_default('ground_fuels', 'duff_depth', 0.05))))
        matl_idx += 1

    matls.append(f"MATL_ID({matl_idx},1) = 'SOIL'")
    thicknesses.append("0.2")

    surf_str = f"&SURF ID = 'Synthetic Ground Fuel',\n"
    surf_str += "      RGB = 101,67,33,\n"
    surf_str += "      " + ",\n      ".join(matls) + ",\n"
    surf_str += "      " + ",\n      ".join(moistures) + ",\n"
    surf_str += "      " + ",\n      ".join(sv_ratios) + ",\n"
    surf_str += "      " + ",\n      ".join(mass_per_vols) + ",\n"
    surf_str += f"      THICKNESS(1:{matl_idx}) = " + ",".join(thicknesses) + " /\n\n"
    
    return surf_str

def generate_bbox_vent(base_bounds: List[float]) -> str:
    x_min, y_min, z_min, x_max, y_max, z_max = base_bounds
    vent_str = "!! SYNTHETIC GROUND FUEL (Bounding Box)\n"
    vent_str += (f"&VENT XB={x_min:.2f},{x_max:.2f},{y_min:.2f},{y_max:.2f},{z_min:.2f},{z_min:.2f}, "
                 f"SURF_ID='Synthetic Ground Fuel' /\n\n")
    return vent_str

def generate_output_blocks(output_params: Any, base_bounds: List[float], fuel_layers: List[Dict[str, Any]]) -> str:
    if not output_params:
        return ""
        
    x_min, y_min, z_min, x_max, y_max, z_max = base_bounds
    y_center = y_min + ((y_max - y_min) / 2)
    
    out_str = "!! REQUESTED OUTPUT DATA\n"

    if safe_get(output_params, 'biomass'):
        out_str += "&BNDF QUANTITY='SURFACE DENSITY', MATL_ID='GENERIC VEGETATION' /\n"
        for layer in fuel_layers:
            name = layer['filename'].replace('.las', '').replace('.txt', '').replace('.laz', '')
            out_str += f"&DEVC ID='{name}_Mass', QUANTITY='PARTICLE MASS', PART_ID='{name}', XYZ={x_min:.2f},{y_center:.2f},{z_min:.2f} /\n"

    if safe_get(output_params, 'hrrpua'):
        out_str += "&BNDF QUANTITY='HRRPUA' /\n"
        
    if safe_get(output_params, 'flame'):
        out_str += f"&SLCF PBY={y_center:.2f}, QUANTITY='HRRPUV' /\n"
        
    if safe_get(output_params, 'temp'):
        out_str += f"&SLCF PBY={y_center:.2f}, QUANTITY='TEMPERATURE' /\n"
        
    if safe_get(output_params, 'wind'):
        out_str += f"&SLCF PBY={y_center:.2f}, QUANTITY='U-VELOCITY', VECTOR=.TRUE. /\n"
        out_str += f"&SLCF PBY={y_center:.2f}, QUANTITY='W-VELOCITY' /\n"
        
    return out_str + "\n"

def assemble_fds_file(output_dir: Union[str, Path], sim_name: str, 
                      base_bounds: List[float], sky_bounds: List[float],
                      forest_bounds: List[float], nx: int, ny: int, nz: int, 
                      fuel_layers: List[Dict[str, Any]], 
                      active_preset: Dict[str, Any], env_params: Any, 
                      ground_fuels: Any, output_params: Any,
                      domain_params: Any, base_voxel: float) -> None:
    assert len(base_bounds) == 6, "Defensive Error: Base bounds array is invalid."
    assert len(fuel_layers) > 0, "Defensive Error: Assembler called with no fuel layers."

    fds_path = Path(output_dir) / f"{sim_name}.fds"
    
    sim_time = safe_get(env_params, 'sim_time', get_default('env_params', 'sim_time', 240.0))
    wind_dev = safe_get(env_params, 'wind_dev_time', get_default('env_params', 'wind_dev_time', 15.0))
    total_time = sim_time + wind_dev
    
    ign_dur = safe_get(env_params, 'ign_duration', get_default('env_params', 'ign_duration', 30.0))
    ign_pattern = safe_get(env_params, 'ign_pattern', get_default('env_params', 'ign_pattern', 'Line: South Edge (y_min)'))
    vent_width = safe_get(env_params, 'vent_width', get_default('env_params', 'vent_width', 1.0))
    
    wind_speed = safe_get(env_params, 'wind_speed', get_default('env_params', 'wind_speed', 3.0))
    wind_dir = safe_get(env_params, 'wind_dir', get_default('env_params', 'wind_dir', 15.0))
    obukhov = safe_get(env_params, 'obukhov', get_default('env_params', 'obukhov', -350.0))
    z0 = safe_get(env_params, 'z0', get_default('env_params', 'z0', 0.5))
    hrrpua = safe_get(env_params, 'hrrpua', get_default('env_params', 'hrrpua', 500.0))

    x_min, y_min, z_min, x_max, y_max, z_max = forest_bounds
    ign_x_min, ign_x_max = x_min, x_max
    ign_y_min, ign_y_max = y_min, y_min + vent_width

    if ign_pattern == 'Line: North Edge (y_max)':
        ign_x_min, ign_x_max = x_min, x_max
        ign_y_min, ign_y_max = y_max - vent_width, y_max
    elif ign_pattern == 'Line: East Edge (x_max)':
        ign_x_min, ign_x_max = x_max - vent_width, x_max
        ign_y_min, ign_y_max = y_min, y_max
    elif ign_pattern == 'Line: South Edge (y_min)':
        ign_x_min, ign_x_max = x_min, x_max
        ign_y_min, ign_y_max = y_min, y_min + vent_width
    elif ign_pattern == 'Line: West Edge (x_min)':
        ign_x_min, ign_x_max = x_min, x_min + vent_width
        ign_y_min, ign_y_max = y_min, y_max
    elif ign_pattern == 'Point: North-East Corner':
        ign_x_min, ign_x_max = x_max - vent_width, x_max
        ign_y_min, ign_y_max = y_max - vent_width, y_max
    elif ign_pattern == 'Point: South-East Corner':
        ign_x_min, ign_x_max = x_max - vent_width, x_max
        ign_y_min, ign_y_max = y_min, y_min + vent_width
    elif ign_pattern == 'Point: South-West Corner':
        ign_x_min, ign_x_max = x_min, x_min + vent_width
        ign_y_min, ign_y_max = y_min, y_min + vent_width
    elif ign_pattern == 'Point: North-West Corner':
        ign_x_min, ign_x_max = x_min, x_min + vent_width
        ign_y_min, ign_y_max = y_max - vent_width, y_max

    with open(fds_path, 'w') as file:
        file.write(f"&HEAD CHID='{sim_name}', TITLE='TLS_to_FDS Generated Simulation' /\\n")
        file.write(f"&TIME T_END={total_time} /\\n\\n")
        
        file.write(generate_mesh_block(base_bounds, sky_bounds, nx, ny, nz, domain_params, base_voxel))
        
        file.write("!! ENVIRONMENT & IGNITION\\n")
        file.write(f"&WIND SPEED={wind_speed:.2f}, DIRECTION={wind_dir:.2f}, L={obukhov:.2f}, Z_0={z0:.2f} /\\n\\n")
        
        file.write(f"&SURF ID='IGN FIRE', HRRPUA={hrrpua:.2f}, COLOR='RED', RAMP_Q='fireramp' /\\n")
        file.write(f"&RAMP ID='fireramp', T={wind_dev:.2f}, F=0.0 /\\n")
        file.write(f"&RAMP ID='fireramp', T={wind_dev + 1.0:.2f}, F=1.0 /\\n")
        file.write(f"&RAMP ID='fireramp', T={wind_dev + ign_dur:.2f}, F=1.0 /\\n")
        file.write(f"&RAMP ID='fireramp', T={wind_dev + ign_dur + 1.0:.2f}, F=0.0 /\\n\\n")
        
        file.write(f"&VENT XB={ign_x_min:.2f},{ign_x_max:.2f},{ign_y_min:.2f},{ign_y_max:.2f},{z_min:.2f},{z_min:.2f}, "
                   f"SURF_ID='IGN FIRE', XYZ={ign_x_min:.2f},{ign_y_min:.2f},{z_min:.2f} /\\n\\n")
        
        if ground_fuels and (safe_get(ground_fuels, 'litter_active', get_default('ground_fuels', 'litter_active', False)) or safe_get(ground_fuels, 'duff_active', get_default('ground_fuels', 'duff_active', False))):
            file.write("!! BOUNDARY FUEL MODEL (LITTER / DUFF)\\n")
            file.write(generate_bfm_surf(ground_fuels, active_preset))
            file.write(generate_bbox_vent(forest_bounds))

        file.write("!! DYNAMIC FUEL LAYERS\\n")
        for layer in fuel_layers:
            file.write(generate_fuel_block(layer, active_preset, env_params))

        if output_params:
            file.write(generate_output_blocks(output_params, forest_bounds, fuel_layers))

        file.write(get_static_boilerplate())
