import laspy
import yaml
import numpy as np
from pathlib import Path
from dendroptimized import voxelize as vox
import utils

def main():
    # Load configuration
    with open("config.yaml", 'r') as f:
        config = yaml.safe_load(f)

    input_dir = Path(config['input_directory'])
    output_dir = Path(config['output_directory'])
    output_dir.mkdir(exist_ok=True)

    # Load datasets
    datasets = []
    filenames = []
    bds = []
    
    for item in config['fuel_layers']:
        path = input_dir / item['filename']
        if path.exists():
            las = laspy.read(path)
            datasets.append(np.vstack((las.x, las.y, las.z)).transpose())
            filenames.append(item['filename'])
            bds.append(item['bulk_density'])

    # Translate to origin
    raw_min, _ = utils.get_global_min_max(datasets)
    translated_datasets = [d - raw_min for d in datasets]

    # Voxelize
    vox_size = config['voxel_size']
    voxels = [vox(d, vox_size, vox_size)[0] for d in translated_datasets]

    # Calc Mesh Bounds
    min_c, max_c = utils.get_global_min_max(voxels)
    nx = int(((max_c[0] - min_c[0]) // vox_size) + 1)
    ny = int(((max_c[1] - min_c[1]) // vox_size) + 1)
    nz = int(((max_c[2] - min_c[2]) // vox_size) + 1)

    # Export FDS Mesh
    utils.write_fds_mesh_config(output_dir, "global_domain", [*min_c, *max_c], nx, ny, nz)

    # Export BDF Files
    for i, data in enumerate(voxels):
        name = Path(filenames[i]).stem
        utils.generate_fortran(name, data, vox_size, bds[i], output_dir)
        print(f"Exported: {name}.bdf")

if __name__ == "__main__":
    main()