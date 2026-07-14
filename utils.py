"""
Utility functions for processing Terrestrial Laser Scanning (TLS) forest point clouds
and exporting them into Fire Dynamics Simulator (FDS) compatible formats.
"""

import numpy as np
import json
from pathlib import Path
from scipy.io import FortranFile
from typing import List, Tuple, Dict, Any, Union

# =============================================================================
# 0. DEFENSIVE HELPERS
# =============================================================================

def safe_get(obj: Any, key: str, default: Any = None) -> Any:
    """
    Safely retrieves a value from either a dictionary or a Dataclass object.
    Prevents AttributeErrors during architecture refactoring.
    
    Args:
        obj (Any): The dictionary or dataclass object to extract from.
        key (str): The string name of the attribute/key.
        default (Any, optional): The fallback value if the key is missing. Defaults to None.
        
    Returns:
        Any: The extracted value, or the default if not found.
    """
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

# =============================================================================
# 1. SPATIAL & BINARY UTILITIES
# =============================================================================

def get_global_min_max(datasets: List[np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculates the global minimum and maximum spatial coordinates across multiple point clouds.

    Args:
        datasets (List[np.ndarray]): A list of 2D numpy arrays representing point clouds.

    Returns:
        Tuple[np.ndarray, np.ndarray]: A tuple containing the (min_coords, max_coords) arrays.
        
    Raises:
        AssertionError: If the datasets list is empty or contains non-arrays.
    """
    assert datasets, "Error: The datasets list cannot be empty."
    assert all(isinstance(d, np.ndarray) for d in datasets), "Error: All datasets must be numpy arrays."
    
    min_coords = np.min([np.min(data, axis=0) for data in datasets], axis=0)
    max_coords = np.max([np.max(data, axis=0) for data in datasets], axis=0)
    return min_coords, max_coords

def generate_fortran(name: str, array_2d: np.ndarray, voxel_size: float, bd: float, output_dir: Union[str, Path]) -> None:
    """
    Exports voxelized fuel data to the FDS Fortran Binary Data Format (.bdf).

    Args:
        name (str): The base name for the output file.
        array_2d (np.ndarray): The [X, Y, Z] coordinates of the voxels.
        voxel_size (float): The uniform 3D size of each voxel in meters.
        bd (float): The bulk density value applied to these voxels.
        output_dir (Union[str, Path]): The directory where the .bdf file will be saved.
        
    Raises:
        AssertionError: If spatial dimensions are invalid or voxel_size is zero/negative.
    """
    assert voxel_size > 0, f"Error: Voxel size must be strictly positive. Got: {voxel_size}"
    assert array_2d.ndim == 2 and array_2d.shape[1] >= 3, "Error: Array must be 2D with at least X, Y, Z columns."
    assert Path(output_dir).exists(), f"Error: Output directory does not exist: {output_dir}"

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
# 2. DOMAIN MATH & ALIGNMENT
# =============================================================================

def calculate_wedding_cake_domain(
    raw_min: np.ndarray, 
    raw_max: np.ndarray, 
    domain_params: Any,
    base_voxel: float
) -> Tuple[List[float], List[float], int, int, int]:
    """
    Calculates aligned bounding boxes for a multi-mesh FDS domain.
    Guarantees no FFT Poisson solver alignment crashes.
    """
    lateral_pad = safe_get(domain_params, 'lateral_pad', 10.0)
    top_pad = safe_get(domain_params, 'top_pad', 20.0)
    sky_mult = safe_get(domain_params, 'sky_multiplier', 2)
    mpi_x = safe_get(domain_params, 'mpi_x', 2)
    mpi_y = safe_get(domain_params, 'mpi_y', 3)
    
    # Snapping: The outer boundaries must be divisible by the coarsest cell 
    # AND divisible by the number of MPI slices to prevent cell straddling!
    snap_x = base_voxel * sky_mult * mpi_x
    snap_y = base_voxel * sky_mult * mpi_y
    snap_z = base_voxel * sky_mult
    
    # 1. Expand raw bounds by the lateral padding
    x_min, y_min = raw_min[0] - lateral_pad, raw_min[1] - lateral_pad
    x_max, y_max = raw_max[0] + lateral_pad, raw_max[1] + lateral_pad
    
    z_min = 0.0 
    base_z_max = raw_max[2] 

    # 2. Push the boundaries outward to the nearest valid interval
    snap_x_min = np.floor(x_min / snap_x) * snap_x
    snap_y_min = np.floor(y_min / snap_y) * snap_y
    snap_x_max = np.ceil(x_max / snap_x) * snap_x
    snap_y_max = np.ceil(y_max / snap_y) * snap_y
    
    snap_base_z_max = np.ceil(base_z_max / snap_z) * snap_z
    snap_sky_z_max = snap_base_z_max + (np.ceil(top_pad / snap_z) * snap_z)

    # 3. Formulate the Boundary Lists
    base_bounds = [snap_x_min, snap_y_min, z_min, snap_x_max, snap_y_max, snap_base_z_max]
    sky_bounds  = [snap_x_min, snap_y_min, snap_base_z_max, snap_x_max, snap_y_max, snap_sky_z_max]

    # 4. Calculate exact cell counts for the base layer
    nx = int(round((snap_x_max - snap_x_min) / base_voxel))
    ny = int(round((snap_y_max - snap_y_min) / base_voxel))
    nz = int(round((snap_base_z_max - z_min) / base_voxel))

    return base_bounds, sky_bounds, nx, ny, nz

def generate_mesh_block(base_bounds: List[float], sky_bounds: List[float], 
                        nx: int, ny: int, nz: int, 
                        domain_params: Any, base_voxel: float) -> str:
    """
    Generates the MESH and VENT configuration string, splitting the domain into 6 parallel meshes.

    Args:
        base_bounds (List[float]): [x_min, y_min, z_min, x_max, y_max, z_max] for the base layer.
        sky_bounds (List[float]): [x_min, y_min, z_min, x_max, y_max, z_max] for the sky layer.
        nx (int): Number of cells in X.
        ny (int): Number of cells in Y.
        nz (int): Number of cells in Z.
        domain_params (Any): Domain parameters.
        base_voxel (float): Base voxel size.

    Returns:
        str: The formatted FDS string for meshes and boundary vents.
    """
    assert len(base_bounds) == 6, f"Error: Expected 6 boundary coordinates, got {len(base_bounds)}"
    assert nx > 0 and ny > 0 and nz > 0, "Error: Mesh cell counts must be greater than zero."

    mpi_x = safe_get(domain_params, 'mpi_x', 2)
    mpi_y = safe_get(domain_params, 'mpi_y', 3)
    sky_mult = safe_get(domain_params, 'sky_multiplier', 2)
    top_pad = safe_get(domain_params, 'top_pad', 20.0)

    x_min, y_min, z_min, x_max, y_max, z_max = base_bounds
    nx_per_mesh = nx // mpi_x
    ny_per_mesh = ny // mpi_y
    
    dx = (x_max - x_min) / mpi_x
    dy = (y_max - y_min) / mpi_y
    
    block = "!! FDS DOMAIN CONFIGURATION\n"
    mesh_idx = 1

    # Generate Base Layer Meshes
    for i in range(mpi_x):
        for j in range(mpi_y):
            xb_min = x_min + (i * dx)
            xb_max = x_min + ((i + 1) * dx)
            yb_min = y_min + (j * dy)
            yb_max = y_min + ((j + 1) * dy)
            block += f"&MESH ID='Base_{mesh_idx}', IJK={nx_per_mesh},{ny_per_mesh},{nz}, XB={xb_min:.2f},{xb_max:.2f},{yb_min:.2f},{yb_max:.2f},{z_min:.2f},{z_max:.2f} /\n"
            mesh_idx += 1
          
    # Generate Sky Layer Mesh
    if top_pad > 0:
        sx_min, sy_min, sz_min, sx_max, sy_max, sz_max = sky_bounds
        sky_voxel = base_voxel * sky_mult
        snx = int(round((sx_max - sx_min) / sky_voxel))
        sny = int(round((sy_max - sy_min) / sky_voxel))
        snz = int(round((sz_max - sz_min) / sky_voxel))
        block += f"&MESH ID='Sky_1', IJK={snx},{sny},{snz}, XB={sx_min:.2f},{sx_max:.2f},{sy_min:.2f},{sy_max:.2f},{sz_min:.2f},{sz_max:.2f} /\n"
        
    block += "\n"
    
    # Vents
    for vent in ['XMIN', 'XMAX', 'YMIN', 'YMAX', 'ZMAX']:
        block += f"&VENT MB='{vent}', SURF_ID='OPEN' /\n"
        
    return block + "\n"

# =============================================================================
# 3. FDS DYNAMIC GENERATION LOGIC
# =============================================================================

def load_preset(preset_name: str, presets_dir: str = "presets") -> Dict[str, Any]:
    """
    Loads a biome fuel properties preset from a JSON file.

    Args:
        preset_name (str): The name of the preset (without .json extension).
        presets_dir (str, optional): The directory containing presets. Defaults to "presets".

    Returns:
        Dict[str, Any]: A dictionary containing the fuel properties.

    Raises:
        FileNotFoundError: If the JSON file does not exist.
        AssertionError: If the preset_name is empty.
    """
    assert preset_name, "Error: Preset name cannot be empty."
    preset_path = Path(presets_dir) / f"{preset_name}.json"
    
    if preset_path.exists():
        with open(preset_path, 'r') as file:
            return json.load(file)
    else:
        raise FileNotFoundError(f"Preset file not found: {preset_path}")

def generate_fuel_block(layer_config: Dict[str, Any], active_preset: Dict[str, Any], env_params: Any) -> str:
    """
    Dynamically generates &SURF, &PART, and &INIT blocks for a single point cloud fuel layer.

    Args:
        layer_config (Dict[str, Any]): Dictionary containing filename and moisture override.
        active_preset (Dict[str, Any]): The loaded JSON preset containing physical properties.
        env_params (Any): Environment configuration (Dict or Dataclass) containing ember settings.

    Returns:
        str: The formatted FDS fuel block.
        
    Raises:
        ValueError: If the semantic class is missing from the JSON preset.
    """
    name = layer_config['filename'].replace('.las', '').replace('.txt', '').replace('.laz', '')
    semantic_class = layer_config.get('semantic_class', 'Canopy')
    bdf_filename = f"{name}.bdf"
    moisture = layer_config.get('moisture_fraction', 0.15)
    
    props = active_preset.get(semantic_class)
    if not props:
        raise ValueError(f"Fuel class '{semantic_class}' not found in the active preset.")
    
    track_embers = safe_get(env_params, 'track_embers', False)
    track_str = "T" if track_embers else "F"
    ember_density = safe_get(env_params, 'ember_density', 62.5)
    ember_velocity = safe_get(env_params, 'ember_velocity', 0.0)
    
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
      EMBER_PARTICLE = {props['ember_particle']}, EMBER_DENSITY_THRESHOLD={ember_density}, EMBER_VELOCITY_THRESHOLD={ember_velocity}, TRACK_EMBERS={track_str} /

&INIT PART_ID='{name}', CELL_CENTERED=.FALSE., BULK_DENSITY_FILE='{bdf_filename}' /
"""
    return block

def get_static_boilerplate() -> str:
    """Returns the static materials and combustion reactions required for FDS wildland fires."""
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
    """
    Generates a stacked Boundary Fuel Model (BFM) &SURF block for Litter and Duff layers.

    Args:
        ground_fuels (Any): Ground fuels configuration containing depths and active flags.
        active_preset (Dict[str, Any]): The loaded JSON preset.

    Returns:
        str: The formatted FDS string for the boundary fuel, or empty if disabled.
    """
    litter_active = safe_get(ground_fuels, 'litter_active', False)
    duff_active = safe_get(ground_fuels, 'duff_active', False)
    
    if not litter_active and not duff_active:
        return ""

    matl_idx = 1
    matls, moistures, sv_ratios, mass_per_vols, thicknesses = [], [], [], [], []

    if litter_active:
        props = active_preset.get("Litter", {})
        matls.append(f"MATL_ID({matl_idx},1) = 'GENERIC VEGETATION'")
        moistures.append(f"MOISTURE_FRACTION({matl_idx}) = {safe_get(ground_fuels, 'litter_moisture')}")
        sv_ratios.append(f"SURFACE_VOLUME_RATIO({matl_idx}) = {props.get('sv_ratio', 6000.0)}")
        mass_per_vols.append(f"MASS_PER_VOLUME({matl_idx}) = {safe_get(ground_fuels, 'litter_bd')}")
        thicknesses.append(str(safe_get(ground_fuels, 'litter_depth')))
        matl_idx += 1

    if duff_active:
        props = active_preset.get("Duff", {})
        matls.append(f"MATL_ID({matl_idx},1) = 'GENERIC VEGETATION'")
        moistures.append(f"MOISTURE_FRACTION({matl_idx}) = {safe_get(ground_fuels, 'duff_moisture')}")
        sv_ratios.append(f"SURFACE_VOLUME_RATIO({matl_idx}) = {props.get('sv_ratio', 8000.0)}")
        mass_per_vols.append(f"MASS_PER_VOLUME({matl_idx}) = {safe_get(ground_fuels, 'duff_bd')}")
        thicknesses.append(str(safe_get(ground_fuels, 'duff_depth')))
        matl_idx += 1

    matls.append(f"MATL_ID({matl_idx},1) = 'SOIL'")
    thicknesses.append("0.2")

    surf_str = f"&SURF ID = 'Synthetic Ground Fuel',\n"
    surf_str += "      " + ",\n      ".join(matls) + ",\n"
    surf_str += "      " + ",\n      ".join(moistures) + ",\n"
    surf_str += "      " + ",\n      ".join(sv_ratios) + ",\n"
    surf_str += "      " + ",\n      ".join(mass_per_vols) + ",\n"
    surf_str += f"      THICKNESS(1:{matl_idx}) = " + ",".join(thicknesses) + " /\n\n"
    
    return surf_str

def generate_bbox_vent(base_bounds: List[float]) -> str:
    """Generates a single &VENT covering the entire computational domain floor."""
    x_min, y_min, z_min, x_max, y_max, z_max = base_bounds
    vent_str = "!! SYNTHETIC GROUND FUEL (Bounding Box)\n"
    vent_str += (f"&VENT XB={x_min:.2f},{x_max:.2f},{y_min:.2f},{y_max:.2f},{z_min:.2f},{z_min:.2f}, "
                 f"SURF_ID='Synthetic Ground Fuel' /\n\n")
    return vent_str

def generate_output_blocks(output_params: Any, base_bounds: List[float], fuel_layers: List[Dict[str, Any]]) -> str:
    """
    Generates FDS &BNDF, &SLCF, and &DEVC files based on user GUI selections.

    Args:
        output_params (Any): Object containing boolean flags for requested outputs.
        base_bounds (List[float]): The 6 coordinates of the computational domain.
        fuel_layers (List[Dict]): The layers currently loaded into the simulation.

    Returns:
        str: Formatted FDS string of output definitions.
    """
    if not output_params:
        return ""
        
    x_min, y_min, z_min, x_max, y_max, z_max = base_bounds
    y_center = y_min + ((y_max - y_min) / 2)
    
    out_str = "!! REQUESTED OUTPUT DATA\n"

    if safe_get(output_params, 'biomass'):
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
    """
    Master assembly function that sequences and compiles all FDS blocks into the final text file.

    Args:
        output_dir (Union[str, Path]): Target directory for the .fds file.
        sim_name (str): The project name (used for the CHID).
        base_bounds (List[float]): Boundaries of the spatial domain.
        nx, ny, nz (int): Discretization cell counts.
        fuel_layers (List[Dict]): Processed point cloud data inputs.
        active_preset (Dict): Loaded JSON preset properties.
        env_params (Any): Atmospheric and ignition parameters.
        ground_fuels (Any, optional): Boundary fuel configurations.
        output_params (Any, optional): GUI requested output slices/devices.
    """
    assert len(base_bounds) == 6, "Defensive Error: Base bounds array is invalid."
    assert len(fuel_layers) > 0, "Defensive Error: Assembler called with no fuel layers."

    fds_path = Path(output_dir) / f"{sim_name}.fds"
    
    # 1. Environment Parsing
    sim_time = safe_get(env_params, 'sim_time', 240.0)
    wind_dev = safe_get(env_params, 'wind_dev_time', 15.0)
    total_time = sim_time + wind_dev
    
    ign_dur = safe_get(env_params, 'ign_duration', 30.0)
    ign_pattern = safe_get(env_params, 'ign_pattern', 'Line: South Edge (y_min)')
    vent_width = safe_get(env_params, 'vent_width', 1.0)
    
    wind_speed = safe_get(env_params, 'wind_speed', 3.0)
    wind_dir = safe_get(env_params, 'wind_dir', 15.0)
    obukhov = safe_get(env_params, 'obukhov', -350.0)
    z0 = safe_get(env_params, 'z0', 0.5)
    hrrpua = safe_get(env_params, 'hrrpua', 500.0)

    # 2. Dynamic Spatial Ignition Logic
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
        file.write(f"&HEAD CHID='{sim_name}', TITLE='TLS_to_FDS Generated Simulation' /\n")
        file.write(f"&TIME T_END={total_time} /\n\n")
        
        file.write(generate_mesh_block(base_bounds, sky_bounds, nx, ny, nz, domain_params, base_voxel))
        
        file.write("!! ENVIRONMENT & IGNITION\n")
        file.write(f"&WIND SPEED={wind_speed:.2f}, DIRECTION={wind_dir:.2f}, L={obukhov:.2f}, Z_0={z0:.2f} /\n\n")
        
        file.write(f"&SURF ID='IGN FIRE', HRRPUA={hrrpua:.2f}, COLOR='RED', RAMP_Q='fireramp' /\n")
        file.write(f"&RAMP ID='fireramp', T={wind_dev:.2f}, F=0.0 /\n")
        file.write(f"&RAMP ID='fireramp', T={wind_dev + 1.0:.2f}, F=1.0 /\n")
        file.write(f"&RAMP ID='fireramp', T={wind_dev + ign_dur:.2f}, F=1.0 /\n")
        file.write(f"&RAMP ID='fireramp', T={wind_dev + ign_dur + 1.0:.2f}, F=0.0 /\n\n")
        
        file.write(f"&VENT XB={ign_x_min:.2f},{ign_x_max:.2f},{ign_y_min:.2f},{ign_y_max:.2f},{z_min:.2f},{z_min:.2f}, "
                   f"SURF_ID='IGN FIRE', XYZ={ign_x_min:.2f},{ign_y_min:.2f},{z_min:.2f} /\n\n")
        
        if ground_fuels and (safe_get(ground_fuels, 'litter_active') or safe_get(ground_fuels, 'duff_active')):
            file.write("!! BOUNDARY FUEL MODEL (LITTER / DUFF)\n")
            file.write(generate_bfm_surf(ground_fuels, active_preset))
            file.write(generate_bbox_vent(forest_bounds))

        file.write("!! DYNAMIC FUEL LAYERS\n")
        for layer in fuel_layers:
            file.write(generate_fuel_block(layer, active_preset, env_params))

        if output_params:
            file.write(generate_output_blocks(output_params, forest_bounds, fuel_layers))

        file.write(get_static_boilerplate())
