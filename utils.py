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

def generate_fuel_block(layer_config, active_preset):
    """
    Dynamically generates &SURF, &PART, and &INIT blocks for a single fuel layer 
    using the externally loaded active_preset.
    """
    name = layer_config['filename'].replace('.las', '').replace('.txt', '')
    semantic_class = layer_config.get('semantic_class', 'Canopy')
    bdf_filename = f"{name}.bdf"
    
    # Fetch properties from the loaded JSON preset
    props = active_preset.get(semantic_class)
    
    if not props:
        raise ValueError(f"Semantic class '{semantic_class}' not found in the active preset.")
    
    block = f"""! --- {semantic_class.upper()}: {name} ---
&SURF ID                      = '{name} surface'
      MATL_ID(1,1)            = 'GENERIC VEGETATION'
      MATL_MASS_FRACTION(1,1) = 1.0
      MOISTURE_FRACTION       = {props['moisture_fraction']}
      SURFACE_VOLUME_RATIO    = {props['sv_ratio']}
      LENGTH                  = {props['length']}
      GEOMETRY                = 'CYLINDRICAL' /

&PART ID='{name}', DRAG_COEFFICIENT={props['drag']}, SAMPLING_FACTOR=1, SURF_ID='{name} surface'
      QUANTITIES='PARTICLE TEMPERATURE','PARTICLE BULK DENSITY', STATIC=.TRUE., COLOR='{props['color']}',
      EMBER_PARTICLE = {props['ember_particle']}, EMBER_DENSITY_THRESHOLD=70, EMBER_VELOCITY_THRESHOLD=0., TRACK_EMBERS={props['track_embers']} /

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

    # Unpack boundaries for dynamic ignition
    x_min, y_min, z_min, x_max, y_max, z_max = global_bounds
    ign_y_max = y_min + 1.0

    with open(fds_path, 'w') as file:
        # 1. Header (Dynamically uses total time)
        file.write(f"&HEAD CHID='{sim_name}', TITLE='TLS_to_FDS Generated Simulation' /\n")
        file.write(f"&TIME T_END={total_time} /\n\n")

        # 2. Domain / Mesh
        file.write(generate_mesh_block(global_bounds, nx, ny, nz))

        # 3. Environment & Ignition
        file.write("!! ENVIRONMENT & IGNITION\n")
        file.write(f"&WIND PRESSURE_GRADIENT_FORCE=0.05, DIRECTION={env_params['wind_dir']}, SPEED={env_params['wind_speed']} /\n\n")
        
        # Ignition Logic
        file.write(f"&SURF ID='IGN FIRE', HRRPUA={env_params['hrrpua']}, COLOR='RED', RAMP_Q='firerampcentre' /\n")
        file.write(f"&RAMP ID='firerampcentre', T=0.0, F=0.0 /\n")
        file.write(f"&RAMP ID='firerampcentre', T={wind_dev}, F=1.0 /\n")
        file.write(f"&RAMP ID='firerampcentre', T={total_time}, F=0.0 /\n")
        file.write(f"&VENT XB={x_min:.2f},{x_max:.2f},{y_min:.2f},{ign_y_max:.2f},{z_min:.2f},{z_min:.2f}, SURF_ID='IGN FIRE', XYZ={x_min:.2f},{y_min:.2f},{z_min:.2f} /\n\n")

        # 4. Dynamic Fuel Layers
        for layer in fuel_layers:
            file.write(generate_fuel_block(layer, active_preset))

        # 5. Static Boilerplate
        file.write(get_static_boilerplate())