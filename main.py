"""
Main execution pipeline converting stratified forest point clouds to FDS voxel configurations.
Reads structural metadata from config.yaml, coordinates translation to origin, voxelizes,
and outputs .bdf and .fds files.
"""

import laspy
import yaml
import numpy as np
from pathlib import Path
from dendroptimized import voxelize as vox
import utils

def main():
    # 1. Pipeline initialization and config configuration loading
    print("Loading pipeline configurations...")
    with open("config.yaml", 'r') as f:
        config = yaml.safe_load(f)

    input_dir = Path(config['input_directory'])
    output_dir = Path(config['output_directory'])
    output_dir.mkdir(exist_ok=True)

    # Load datasets
    datasets = []
    filenames = []
    bds = []
    
    # 2. Ingest structured fuel layers
    print("Ingesting stratified point cloud layers...")
    for item in config['fuel_layers']:
        path = input_dir / item['filename']
        if path.exists():
            las = laspy.read(path)
            datasets.append(np.vstack((las.x, las.y, las.z)).transpose())
            filenames.append(item['filename'])
            bds.append(item['bulk_density'])

    # 3. Coordinate Translation to Origin
    # Map real-world geographical coordinates safely to (0,0,0) for FDS stability.
    print("Normalizing spatial coordinates to the local origin (0,0,0)...")
    raw_min, _ = utils.get_global_min_max(datasets)
    translated_datasets = [d - raw_min for d in datasets]
 
    # 4. Voxelization
    print("Executing 3D spatial voxelization...")
    vox_size = config['voxel_size']
    voxels = [vox(d, vox_size, vox_size)[0] for d in translated_datasets]

    # 5. Domain boundary evaluation and mesh assignment
    print("Calculating domain grid dimensions...")
    min_c, max_c = utils.get_global_min_max(voxels)
    nx = int(((max_c[0] - min_c[0]) // vox_size) + 1)
    ny = int(((max_c[1] - min_c[1]) // vox_size) + 1)
    nz = int(((max_c[2] - min_c[2]) // vox_size) + 1)

    # 6. Technical File Exports
    print("Exporting FDS computational domain file (.fds)...")
    utils.write_fds_mesh_config(output_dir, "global_domain", [*min_c, *max_c], nx, ny, nz)

    # Export BDF Files
    for i, data in enumerate(voxels):
        name = Path(filenames[i]).stem
        utils.generate_fortran(name, data, vox_size, bds[i], output_dir)
        print(f"Exported: {name}.bdf")
    
    print("\nProcessing pipeline complete. Output files are available in:", output_dir.resolve())

if __name__ == "__main__":
    main()