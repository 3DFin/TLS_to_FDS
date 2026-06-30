"""
Main execution pipeline converting stratified forest point clouds to FDS voxel configurations.
"""

import laspy
import numpy as np
from pathlib import Path
from dendroptimized import voxelize as vox
import utils

def run_pipeline(config, log_callback=print):
    """
    Executes the conversion pipeline using a configuration dictionary passed from the GUI.
    Accepts an optional log_callback function to redirect console print statements to the GUI.
    """
    log_callback("Loading pipeline configurations...")

    input_dir = Path(config['input_directory'])
    output_dir = Path(config['output_directory'])
    output_dir.mkdir(exist_ok=True)

    # Load datasets
    datasets = []
    filenames = []
    bds = []
    
    log_callback("Ingesting stratified point cloud layers...")
    for item in config['fuel_layers']:
        path = input_dir / item['filename']
        if path.exists():
            las = laspy.read(path)
            datasets.append(np.vstack((las.x, las.y, las.z)).transpose())
            filenames.append(item['filename'])
            bds.append(item['bulk_density'])
        else:
            log_callback(f"Warning: File not found {path}")

    if not datasets:
        log_callback("Error: No valid point cloud datasets loaded.")
        return

    # Coordinate Translation to Origin
    log_callback("Normalizing spatial coordinates to the local origin (0,0,0)...")
    raw_min, _ = utils.get_global_min_max(datasets)
    translated_datasets = [d - raw_min for d in datasets]
 
    # Voxelization
    log_callback("Executing 3D spatial voxelization...")
    vox_size = config['voxel_size']
    voxels = [vox(d, vox_size, vox_size)[0] for d in translated_datasets]

    # Domain boundary evaluation and mesh assignment
    log_callback("Calculating domain grid dimensions...")
    min_c, max_c = utils.get_global_min_max(voxels)
    nx = int(((max_c[0] - min_c[0]) // vox_size) + 1)
    ny = int(((max_c[1] - min_c[1]) // vox_size) + 1)
    nz = int(((max_c[2] - min_c[2]) // vox_size) + 1)

    # --- NEW PRESET LOGIC ---
    preset_name = config.get('preset_name')
    if not preset_name or preset_name == "No presets found":
        log_callback("Error: Cannot generate FDS without a valid biome preset.")
        return
        
    try:
        log_callback(f"Loading biome properties from preset: {preset_name}.json")
        active_preset = utils.load_preset(preset_name)
    except Exception as e:
        log_callback(f"Failed to load preset: {str(e)}")
        return

    # Technical File Exports
    log_callback("Exporting FDS computational domain file (.fds)...")
    
    # Note: Ensure utils.assemble_fds_file is updated to accept active_preset
    utils.assemble_fds_file(
        output_dir, 
        "global_domain", 
        [*min_c, *max_c], 
        nx, ny, nz, 
        config['fuel_layers'],
        active_preset,
        config.get('env_params'),
    )

    log_callback("Generating Fortran Binary Data Files (.bdf) for FDS...")
    for name, vox_data, bd in zip(filenames, voxels, bds):
        clean_name = Path(name).stem
        utils.generate_fortran(clean_name, vox_data, vox_size, bd, output_dir)

    log_callback("FDS Generation Complete!")

if __name__ == "__main__":
    # Fallback to loading standard yaml if run directly outside the GUI
    import yaml
    with open("config.yaml", 'r') as f:
        cfg = yaml.safe_load(f)
    run_pipeline(cfg)