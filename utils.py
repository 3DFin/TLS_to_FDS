"""
Utility functions for processing Terrestrial Laser Scanning (TLS) forest point clouds
and exporting them into Fire Dynamics Simulator (FDS) compatible formats.
"""
import numpy as np
from pathlib import Path
from scipy.io import FortranFile

def get_global_min_max(datasets):
    """
    Calculate the global minimum and maximum coordinates across multiple 3D datasets.

    This ensures a unified bounding box can be established when handling separate
    fuel layers (e.g., ground, canopy, stems).

    Parameters:
        datasets (list of np.ndarray): List of Nx3 arrays representing point clouds [[x, y, z], ...].

    Returns:
        tuple: (min_coords, max_coords) as 1D numpy arrays of length 3 (X, Y, Z).
    """
    min_coords = np.min([np.min(data, axis=0) for data in datasets], axis=0)
    max_coords = np.max([np.max(data, axis=0) for data in datasets], axis=0)
    return min_coords, max_coords

def generate_fortran(name, array_2d, voxel_size, bd, output_dir):
    """
    Export voxelized fuel data to the FDS Fortran Binary Data Format (.bdf).

    FDS processes discrete vegetation using binary record structures. This function
    writes out the bounding faces of the voxelized layer, the resolution, the total 
    number of active voxels, and the center coordinates paired with bulk density.

    Parameters:
        name (str): Base name for the output .bdf file.
        array_2d (np.ndarray): Nx3 array of voxel centers [[x, y, z], ...].
        voxel_size (float): The grid resolution in meters (isotropic).
        bd (float): Bulk density assigned to the voxels (kg/m^3).
        output_dir (Path or str): Directory where the .bdf file will be written.
    """
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
    """
    Generate an FDS input snippet (.fds) setting up the computational domain.

    Automating this ensures that the fluid dynamics grid perfectly aligns with 
    the boundaries of the underlying voxelized fuel data. The domain is sliced 
    into 6 equal segments along the X-axis to prepare for parallel MPI processing.

    Parameters:
        output_dir (Path or str): Directory to save the resulting script.
        name (str): Base name for the output .fds file.
        global_bounds (list/np.ndarray): Unified coordinates [xmin, ymin, zmin, xmax, ymax, zmax].
        nx, ny, nz (int): Calculated grid counts for a single mesh segment.
    """
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