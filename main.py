"""
Main execution pipeline converting forest point clouds to FDS voxel configurations.
"""
import time
import laspy
import numpy as np
from pathlib import Path
from typing import Any, Callable

from dendroptimized import voxelize as vox
import utils

def run_pipeline(config: Any, log_callback: Callable[[str], None] = print, progress_callback: Callable[[int], None] = None) -> None:
    """
    Executes the 3D conversion pipeline to generate FDS computational domains.
    
    Args:
        config (Any): The runtime configuration (Dataclass from GUI, or Dict from YAML).
        log_callback (Callable): Function to redirect print statements to the GUI console.
        progress_callback (Callable): Function to update progress bar.
        
    Raises:
        AssertionError: If critical path or layer data is missing from the configuration.
    """
    def update_progress(percent: int):
        if progress_callback:
            progress_callback(percent)

    log_callback("Loading pipeline configurations...")
    update_progress(5) # Immediate 5% progress so the user sees it moving

    # Using safe_get to support both Dataclasses (GUI) and Dictionaries (Terminal/YAML)
    input_dir_str = utils.safe_get(config, 'input_directory')
    output_dir_str = utils.safe_get(config, 'output_directory')
    fuel_layers = utils.safe_get(config, 'fuel_layers', [])
    vox_size = utils.safe_get(config, 'voxel_size', 0.2)
    preset_name = utils.safe_get(config, 'preset_name')
    output_name = utils.safe_get(config, 'output_filename', 'model')

    # Pre-flight Checks
    assert input_dir_str, "Defensive Error: Input directory is missing from configuration."
    assert output_dir_str, "Defensive Error: Output directory is missing from configuration."
    assert fuel_layers, "Defensive Error: Fuel layers list cannot be empty."
    
    # --- PRESET LOGIC ---
    if not preset_name or preset_name == "No forest presets found":
        log_callback("Error: Cannot generate FDS without a valid biome preset.")
        update_progress(0)
    try:
        log_callback(f"Loading biome properties from preset: {preset_name}.json")
        active_preset = utils.load_preset(preset_name)
    except Exception as e:
        log_callback(f"Failed to load preset: {str(e)}")
        return

    input_dir = Path(input_dir_str)
    output_dir = Path(output_dir_str)
    # parents=True ensures it creates nested folders safely if they don't exist
    output_dir.mkdir(parents=True, exist_ok=True) 

    # Load datasets
    datasets = []
    filenames = []
    bds = []
    
    # PROGRESS LOOP 1: Ingesting Data (10% to 30%)
    log_callback("Ingesting Forest Fuel Layers...")
    total_files = len(fuel_layers)

    for idx, item in enumerate(fuel_layers):
        # Calculate progress step for this file
        current_prog = 10 + int((idx / total_files) * 20)
        update_progress(current_prog)

        # Since fuel_layers is a List of Dictionaries, standard .get() applies here
        filename = item.get('filename')
        bulk_density = item.get('bulk_density')
        path = input_dir / filename
        log_callback(f"  -> Reading point cloud: {filename}...")
        
        if path.exists():
            try:
                start_time = time.time()
                las = laspy.read(path)
                points_extracted = len(las.x)
                datasets.append(np.vstack((las.x, las.y, las.z)).transpose())
                filenames.append(filename)
                bds.append(bulk_density)

                elapsed = time.time() - start_time
                log_callback(f"     [SUCCESS] Extracted {points_extracted:,} points in {elapsed:.2f} seconds.")
            except Exception as e:
                log_callback(f"     Error reading {filename}: {str(e)}")
        else:
            log_callback(f"Warning: File not found {path}")

    if not datasets:
        log_callback("Error: No valid point cloud datasets loaded. Aborting pipeline.")
        update_progress(0)
        return

    # Coordinate Translation to Origin
    update_progress(30)
    log_callback("Normalizing spatial coordinates to the local origin (0,0,0)...")
    raw_min, _ = utils.get_global_min_max(datasets)
    translated_datasets = [d - raw_min for d in datasets]
    
    # PROGRESS LOOP 2: Voxelization (30% to 70%)
    log_callback("Executing 3D spatial voxelization...")
    voxels = []
    
    for idx, (d, name) in enumerate(zip(translated_datasets, filenames)):
        # Calculate progress step for this voxelization
        current_prog = 30 + int((idx / total_files) * 40)
        update_progress(current_prog)

        start_time = time.time()
        # Voxelize the layer (using with_n_points=False)
        v_data = vox(d, vox_size, vox_size, with_n_points=False)[0]
        voxels.append(v_data)
        
        elapsed = time.time() - start_time
        num_voxels = len(v_data)
        
        log_callback(f"     [SUCCESS] {name}: Generated {num_voxels:,} voxels in {elapsed:.2f} seconds.")

    update_progress(75)

    # CALCULATE DOMAIN PADDING & ALIGNMENT ---
    log_callback("Calculating mathematically aligned Domain and Sky padding...")
    
    # We pull the raw mins/maxs of the translated voxels to build the padding around
    translated_min, translated_max = utils.get_global_min_max(voxels)
    domain_params = utils.safe_get(config, 'domain_params')

    base_bounds, sky_bounds, nx, ny, nz = utils.calculate_wedding_cake_domain(
        translated_min, translated_max, domain_params, vox_size
    )

    # Technical File Exports
    update_progress(80)
    log_callback("Exporting FDS computational domain file (.fds)...")

    # Safely extract the optional FDS configuration modules
    env_params = utils.safe_get(config, 'env_params')
    ground_fuels = utils.safe_get(config, 'ground_fuels')
    output_params = utils.safe_get(config, 'output_params')

    utils.assemble_fds_file(
        output_dir=output_dir,
        sim_name=output_name,
        base_bounds=base_bounds,
        sky_bounds=sky_bounds,
        nx=nx, ny=ny, nz=nz,
        fuel_layers=fuel_layers,
        active_preset=active_preset,
        env_params=env_params,
        ground_fuels=ground_fuels,
        output_params=output_params,
        domain_params=domain_params,
        base_voxel=vox_size
    )

    # PROGRESS LOOP 3: Fortran Exports (85% to 95%
    log_callback("Generating Fortran Binary Data Files (.bdf) for FDS...")
    for idx, (name, vox_data, bd) in enumerate(zip(filenames, voxels, bds)):
        current_prog = 85 + int((idx / total_files) * 10)
        update_progress(current_prog)

        clean_name = Path(name).stem
        start_time = time.time()
        utils.generate_fortran(clean_name, vox_data, vox_size, bd, output_dir)
        elapsed = time.time() - start_time
        
        log_callback(f"     [SUCCESS] Exported {clean_name}.bdf in {elapsed:.2f} seconds.")

    update_progress(100)
    log_callback("FDS Generation Complete!")

    # --- Generate Run Command ---
    fds_filename = f"{output_name}.fds"
    # Calculate how many CPUs this simulation requires
    mpi_x = utils.safe_get(domain_params, 'mpi_x', 2)
    mpi_y = utils.safe_get(domain_params, 'mpi_y', 3)
    has_sky = 1 if utils.safe_get(domain_params, 'top_pad', 20.0) > 0 else 0
    total_processors = (mpi_x * mpi_y) + has_sky

    run_command = f"fds_local -p {total_processors} -o 1 {fds_filename}"
    
    # 1. Print to the GUI Console
    log_callback("-" * 40)
    log_callback("READY TO RUN! Execute this command in your FDS terminal:")
    log_callback(f"   {run_command}")
    log_callback("-" * 40)
    
    # 2. Save to a .txt file in the output directory
    cmd_file_path = output_dir / "run_command.txt"
    try:
        with open(cmd_file_path, 'w') as cmd_file:
            cmd_file.write("To run this simulation, open your terminal/command prompt in this directory and run:\n\n")
            cmd_file.write(run_command)
    except Exception as e:
        log_callback(f"Warning: Could not write run_command.txt: {e}")

if __name__ == "__main__":
    # Fallback to loading standard yaml if run directly outside the GUI terminal
    import yaml
    with open("config.yaml", 'r') as f:
        cfg = yaml.safe_load(f)
    run_pipeline(cfg)