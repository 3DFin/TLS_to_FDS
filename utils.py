"""
Utility functions for processing Terrestrial Laser Scanning (TLS) forest point clouds
and exporting them into Fire Dynamics Simulator (FDS) compatible formats.
"""
import numpy as np
from pathlib import Path
from scipy.io import FortranFile
import json
# =============================================================================
# 1. SPATIAL & BINARY UTILITIES
# =============================================================================

def get_global_min_max(datasets):
    """Calculate the global minimum and maximum coordinates across multiple 3D datasets."""
    min_coords = np.min([np.min(data, axis=0) for data in datasets], axis=0)
    max_coords = np.max([np.max(data, axis=0) for data in datasets], axis=0)
    return min_coords, max_coords

def generate_fortran(name, array_2d, voxel_size, bd, output_dir):
    """Export voxelized fuel data to the FDS Fortran Binary Data Format (.bdf)."""
    file_path = Path(output_dir) / f"{name}.bdf"
    f = FortranFile(file_path, 'w')
    
    n = array_2d.shape[0]
    x, y, z = array_2d[:, 0], array_2d[:, 1], array_2d[:, 2]
    
    bounds = np.array([
        min(x)-voxel_size/2, max(x)+voxel_size/2,
        min(y)-voxel_size/2, max(y)+voxel_size/2,
        min(z)-voxel_size/2, max(z)+voxel_size/2
    ], dtype=np.float64)

    f.write_record(bounds)
    f.write_record(np.array([voxel_size]*3, dtype=np.float64))
    f.write_record(np.array(n, dtype=np.int32))
    
    for i in range(n):
        f.write_record(array_2d[i].astype(np.float64))
        f.write_record(np.array(bd, dtype=np.float64))
    f.close()


# =============================================================================
# 2. FDS DYNAMIC GENERATION LOGIC
# =============================================================================

def load_preset(preset_name, presets_dir="presets"):
    """Loads a biome preset JSON file into a Python dictionary."""
    preset_path = Path(presets_dir) / f"{preset_name}.json"
    if preset_path.exists():
        with open(preset_path, 'r') as file:
            return json.load(file)
    else:
        raise FileNotFoundError(f"Preset file not found: {preset_path}")

def generate_mesh_block(global_bounds, nx, ny, nz):
    """Generate the MESH and VENT configuration string."""
    x_min, y_min, z_min, x_max, y_max, z_max = global_bounds
    x_range = x_max - x_min
    x_segment = x_range / 6

    block = "!! FDS DOMAIN CONFIGURATION\n"
    for i in range(6):
        xb_min = x_min + i * x_segment
        xb_max = x_min + (i + 1) * x_segment
        block += f"&MESH IJK={nx},{ny},{nz}, XB={xb_min:.2f},{xb_max:.2f},{y_min:.2f},{y_max:.2f},{z_min:.2f},{z_max:.2f} /\n"
    
    # Standard vents
    for vent in ['XMIN', 'XMAX', 'YMIN', 'YMAX', 'ZMAX']:
        block += f"&VENT MB='{vent}', SURF_ID='OPEN' /\n"
    return block + "\n"

def generate_fuel_block(layer_config, active_preset, env_params):
    """
    Dynamically generates &SURF, &PART, and &INIT blocks for a single fuel layer 
    using the externally loaded active_preset.
    """
    name = layer_config['filename'].replace('.las', '').replace('.txt', '')
    semantic_class = layer_config.get('semantic_class', 'Canopy')
    bdf_filename = f"{name}.bdf"
    
    moisture = layer_config.get('moisture_fraction', 0.15)
    # Fetch properties from the loaded JSON preset
    props = active_preset.get(semantic_class)
    
    # Ember params
    track_embers = env_params.get('track_embers', False)
    track_str = "T" if track_embers else "F"
    ember_density = env_params.get('ember_density', 62.5)
    ember_velocity = env_params.get('ember_velocity', 0.0)
    
    if not props:
        raise ValueError(f"Fuel class '{semantic_class}' not found in the active preset.")
    
    block = f"""! --- {semantic_class.upper()}: {name} ---
&SURF ID                      = '{name} surface'
      MATL_ID(1,1)            = 'GENERIC VEGETATION'
      MATL_MASS_FRACTION(1,1) = 1.0
      MOISTURE_FRACTION       = {moisture}
      SURFACE_VOLUME_RATIO    = {props['sv_ratio']}
      LENGTH                  = {props['length']}
      GEOMETRY                = 'CYLINDRICAL' /

&PART ID='{name}', DRAG_COEFFICIENT={props['drag']}, SAMPLING_FACTOR=1, SURF_ID='{name} surface'
      QUANTITIES='PARTICLE TEMPERATURE','PARTICLE BULK DENSITY', STATIC=.TRUE., COLOR='{props['color']}',
      EMBER_PARTICLE = {props['ember_particle']}, EMBER_DENSITY_THRESHOLD={ember_density}, EMBER_VELOCITY_THRESHOLD={ember_velocity}, TRACK_EMBERS='{track_str}' /

&INIT PART_ID='{name}', CELL_CENTERED=.FALSE., BULK_DENSITY_FILE='{bdf_filename}' /
"""
    return block

def get_static_boilerplate():
    """Returns the static materials, reactions, and outputs."""
    return """
!! STATIC MATERIALS AND REACTIONS
&REAC FUEL='FUEL VAPOR', C=2.10, H=6.20, O=2.16, SOOT_YIELD=0.01, HEAT_OF_COMBUSTION=17425., IDEAL=T /
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
      A                  = 465.
      E                  = 68000.
      SPEC_ID               = 'PRODUCTS','AIR'
      NU_SPEC               = 8.13,-7.17
      MATL_ID               = 'ASH'
      NU_MATL               = 0.04
      HEAT_OF_REACTION      = -25000. /

&MATL ID                    = 'ASH'
      DENSITY               = 67.
      CONDUCTIVITY          = 0.1
      SPECIFIC_HEAT_RAMP    = 'c_v' /

&RAMP ID='c_v', T=  0., F=1.1 /
&RAMP ID='c_v', T=200., F=2.0 /
&RAMP ID='c_v', T=800., F=2.0 /

&TAIL /
"""

def assemble_fds_file(output_dir, sim_name, global_bounds, nx, ny, nz, fuel_layers, active_preset, env_params):
    """Master function to assemble and write the final .fds file."""
    fds_path = Path(output_dir) / f"{sim_name}.fds"
    
    # Fallback in case env_params fails to pass
    if not env_params:
        env_params = {"sim_time": 240, "wind_dev_time": 15, "wind_dir": 15, "wind_speed": 3, "hrrpua": 500}

    total_time = env_params['sim_time'] + env_params['wind_dev_time']
    wind_dev = env_params['wind_dev_time']
    ign_dur = env_params.get('ign_duration', 30.0)
    ign_pattern = env_params.get('ign_pattern', 'Line: South Edge (y_min)')

    # --- DYNAMIC SPATIAL IGNITION LOGIC ---

    # Initialize default bounds (will be overwritten based on pattern)
    x_min, y_min, z_min, x_max, y_max, z_max = global_bounds
    vent_width = env_params.get('vent_width', 1.0)
    
    # Initialize default bounds (Safety fallback)
    ign_x_min, ign_x_max = x_min, x_max
    ign_y_min, ign_y_max = y_min, y_min + vent_width

    # Ignition Lines    
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
    
    # Corner fires
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
        # 1. Header (Dynamically uses total time)
        file.write(f"&HEAD CHID='{sim_name}', TITLE='TLS_to_FDS Generated Simulation' /\n")
        file.write(f"&TIME T_END={total_time} /\n\n")

        # 2. Domain / Mesh
        file.write(generate_mesh_block(global_bounds, nx, ny, nz))

        # 3. Environment & Ignition
        file.write("!! ENVIRONMENT & IGNITION\n")
        file.write(f"&WIND SPEED={env_params['wind_speed']:.2f}, DIRECTION={env_params['wind_dir']:.2f}, "
                   f"L={env_params['obukhov']:.2f}, Z_0={env_params['z0']:.2f} /\n\n")
        
        file.write(f"&SURF ID='IGN FIRE', HRRPUA={env_params['hrrpua']:.2f}, COLOR='RED', RAMP_Q='fireramp' /\n")
        
        # Ignition Ramp Logic: Wait for wind, ramp to 1.0, hold for duration, shut off.
        file.write(f"&RAMP ID='fireramp', T={wind_dev:.2f}, F=0.0 /\n")
        file.write(f"&RAMP ID='fireramp', T={wind_dev + 1.0:.2f}, F=1.0 /\n")
        file.write(f"&RAMP ID='fireramp', T={wind_dev + ign_dur:.2f}, F=1.0 /\n")
        file.write(f"&RAMP ID='fireramp', T={wind_dev + ign_dur + 1.0:.2f}, F=0.0 /\n\n")
        
        file.write(f"&VENT XB={ign_x_min:.2f},{ign_x_max:.2f},{ign_y_min:.2f},{ign_y_max:.2f},{z_min:.2f},{z_min:.2f}, "
                   f"SURF_ID='IGN FIRE', XYZ={ign_x_min:.2f},{ign_y_min:.2f},{z_min:.2f} /\n\n")

        # 4. Dynamic Fuel Layers
        file.write("!! DYNAMIC FUEL LAYERS\n")
        for layer in fuel_layers:
            # We pass the entire env_params dictionary down
            file.write(generate_fuel_block(layer, active_preset, env_params))

        # 5. Static Boilerplate
        file.write(get_static_boilerplate())