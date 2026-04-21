import numpy as np
from pathlib import Path
from scipy.io import FortranFile

def get_global_min_max(datasets):
    min_coords = np.min([np.min(data, axis=0) for data in datasets], axis=0)
    max_coords = np.max([np.max(data, axis=0) for data in datasets], axis=0)
    return min_coords, max_coords

def generate_fortran(name, array_2d, voxel_size, bd, output_dir):
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

def write_fds_mesh_config(output_dir, name, global_bounds, nx, ny, nz):
    x_min, y_min, z_min, x_max, y_max, z_max = global_bounds
    x_range = x_max - x_min
    x_segment = x_range / 6

    domain_file_path = Path(output_dir) / f"{name}.fds"
    with open(domain_file_path, 'w') as file:
        file.write("!! FDS DOMAIN CONFIGURATION\n")
        for i in range(6):
            xb_min = x_min + i * x_segment
            xb_max = x_min + (i + 1) * x_segment
            file.write(f"&MESH IJK={nx},{ny},{nz}, XB={xb_min:.2f},{xb_max:.2f},{y_min:.2f},{y_max:.2f},{z_min:.2f},{z_max:.2f} /\n")
        # Standard vents
        for vent in ['XMIN', 'XMAX', 'YMIN', 'YMAX', 'ZMAX']:
            file.write(f"&VENT MB='{vent}', SURF_ID='OPEN' /\n")