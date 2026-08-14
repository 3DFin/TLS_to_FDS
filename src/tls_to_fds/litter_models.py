"""Dynamic Ground Fuel Litter Accumulation Models.

Provides decoupled scientific models for computing 2D spatial distributions
of ground fuel (litter/duff) load and bulk density:
- Model i (TreeDistanceLitterModel): Tree map distance-decay function.
- Model ii (CanopyTurnoverLitterModel): Vertical canopy integration with point-density
  weighted bulk density scaling and 2D Gaussian dispersion convolution.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter


def load_tree_map(file_path: str | Path) -> np.ndarray:
    """Parses a tree map file (.csv, .txt, or .las) and returns stem (X, Y) coordinates.

    Parameters
    ----------
    file_path : str or Path
        Path to the tree map file.

    Returns
    -------
    np.ndarray
        Array of shape (N, 2) containing (X, Y) tree stem positions.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Tree map file not found: {file_path}")

    suffix = path.suffix.lower()

    if suffix in [".las", ".laz"]:
        import laspy

        las = laspy.read(path)
        return np.vstack((las.x, las.y)).T

    elif suffix in [".csv", ".txt", ".xyz", ".asc"]:
        content = path.read_text(encoding="utf-8-sig", errors="ignore")[:1000]
        # Detect delimiter: semicolon, comma, tab, or whitespace
        first_line = content.strip().splitlines()[0] if content.strip() else ""
        if ";" in first_line:
            delim = ";"
        elif "," in first_line:
            delim = ","
        elif "\t" in first_line:
            delim = "\t"
        else:
            delim = None  # whitespace

        # Try reading structured table with headers (e.g. x, y columns)
        try:
            data = np.genfromtxt(
                path, delimiter=delim, names=True, encoding="utf-8-sig"
            )
            if data is not None and data.dtype.names:
                names = [n.lower().strip() for n in data.dtype.names]
                if "x" in names and "y" in names:
                    x_col = [n for n in data.dtype.names if n.lower().strip() == "x"][0]
                    y_col = [n for n in data.dtype.names if n.lower().strip() == "y"][0]
                    return np.vstack((data[x_col], data[y_col])).T
        except Exception:
            pass

        # Check if first line is a non-numeric header
        skip_header = 0
        if first_line:
            parts = [
                p.strip().lstrip("\ufeff")
                for p in (first_line.split(delim) if delim else first_line.split())
            ]
            if len(parts) >= 2:
                try:
                    float(parts[0])
                    float(parts[1])
                    skip_header = 0
                except ValueError:
                    skip_header = 1

        raw = np.loadtxt(
            path, delimiter=delim, skiprows=skip_header, encoding="utf-8-sig"
        )
        if raw.ndim == 1:
            raw = raw.reshape(1, -1)
        return raw[:, :2]

    else:
        raise ValueError(f"Unsupported tree map file extension: {suffix}")


def load_dtm(file_path: str | Path) -> np.ndarray:
    """Parses a 3DFin DTM file (.csv, .txt, .asc, .xyz, .las, .laz, .obj) returning (N, 3) XYZ ground points.

    Parameters
    ----------
    file_path : str or Path
        Path to DTM file.

    Returns
    -------
    np.ndarray
        Array of shape (N, 3) containing (X, Y, Z) ground surface points.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"DTM file not found: {file_path}")

    suffix = path.suffix.lower()

    if suffix in [".las", ".laz"]:
        import laspy

        las = laspy.read(path)
        return np.vstack((las.x, las.y, las.z)).T

    elif suffix == ".obj":
        vertices = []
        with open(path, encoding="utf-8-sig", errors="ignore") as f:
            for line in f:
                if line.startswith("v "):
                    parts = line.strip().split()
                    vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
        if not vertices:
            raise ValueError(f"No vertices ('v x y z') found in OBJ file: {file_path}")
        return np.array(vertices, dtype=float)

    elif suffix in [".csv", ".txt", ".xyz", ".asc"]:
        content = path.read_text(encoding="utf-8-sig", errors="ignore")[:1000]
        # Detect delimiter: semicolon, comma, tab, or whitespace
        first_line = content.strip().splitlines()[0] if content.strip() else ""
        if ";" in first_line:
            delim = ";"
        elif "," in first_line:
            delim = ","
        elif "\t" in first_line:
            delim = "\t"
        else:
            delim = None  # whitespace

        try:
            data = np.genfromtxt(
                path, delimiter=delim, names=True, encoding="utf-8-sig"
            )
            if data is not None and data.dtype.names:
                names = [n.lower().strip() for n in data.dtype.names]
                if "x" in names and "y" in names and "z" in names:
                    x_col = [n for n in data.dtype.names if n.lower().strip() == "x"][0]
                    y_col = [n for n in data.dtype.names if n.lower().strip() == "y"][0]
                    z_col = [n for n in data.dtype.names if n.lower().strip() == "z"][0]
                    return np.vstack((data[x_col], data[y_col], data[z_col])).T
        except Exception:
            pass

        # Check if first line is a non-numeric header
        skip_header = 0
        if first_line:
            parts = [
                p.strip().lstrip("\ufeff")
                for p in (first_line.split(delim) if delim else first_line.split())
            ]
            if len(parts) >= 3:
                try:
                    float(parts[0])
                    float(parts[1])
                    float(parts[2])
                    skip_header = 0
                except ValueError:
                    skip_header = 1

        raw = np.loadtxt(
            path, delimiter=delim, skiprows=skip_header, encoding="utf-8-sig"
        )
        if raw.ndim == 1:
            raw = raw.reshape(1, -1)
        return raw[:, :3]
    else:
        raise ValueError(f"Unsupported DTM file extension: {suffix}")


def build_litter_bdf_voxels(
    litter_2d_density: np.ndarray,
    domain_bounds: tuple[float, float, float, float, float, float],
    voxel_sizes: tuple[float, float, float],
    litter_depth: float = 0.05,
    dtm_points: np.ndarray | None = None,
) -> np.ndarray:
    """Extrudes a 2D spatial litter bulk density grid into a 3D voxel array (nz, ny, nx) anchored to DTM elevation.

    Parameters
    ----------
    litter_2d_density : np.ndarray
        2D spatial litter bulk density grid of shape (ny, nx).
    domain_bounds : tuple of float
        (x_min, y_min, z_min, x_max, y_max, z_max)
    voxel_sizes : tuple of float
        (dx, dy, dz) voxel dimensions.
    litter_depth : float
        Physical depth/thickness of the litter layer (meters).
    dtm_points : np.ndarray, optional
        Array of shape (N, 3) containing (X, Y, Z) DTM points. If None, z_min is used as flat ground.

    Returns
    -------
    np.ndarray
        3D voxel array of shape (nz, ny, nx) containing bulk density values for Litter.bdf.
    """
    x_min, y_min, z_min, _x_max, _y_max, z_max = domain_bounds
    dx, dy, dz = voxel_sizes

    ny, nx = litter_2d_density.shape
    nz = max(1, round((z_max - z_min) / dz))

    v_grid = np.zeros((nz, ny, nx), dtype=float)

    # Calculate 2D ground elevation grid Z_ground(y, x)
    z_ground = np.full((ny, nx), z_min, dtype=float)

    if dtm_points is not None and len(dtm_points) > 0:
        # Interpolate or map DTM points to 2D grid cells
        dtm_x, dtm_y, dtm_z = dtm_points[:, 0], dtm_points[:, 1], dtm_points[:, 2]
        ix = np.clip(((dtm_x - x_min) / dx).astype(int), 0, nx - 1)
        iy = np.clip(((dtm_y - y_min) / dy).astype(int), 0, ny - 1)

        for x_i, y_i, z_v in zip(ix, iy, dtm_z):
            if z_ground[y_i, x_i] == z_min or z_v < z_ground[y_i, x_i]:
                z_ground[y_i, x_i] = z_v

    # Populate 3D voxels for cells within [z_ground, z_ground + litter_depth]
    z_coords = np.arange(z_min + dz / 2, z_max, dz)

    for j in range(ny):
        for i in range(nx):
            density = litter_2d_density[j, i]
            if density <= 0:
                continue

            z_bot = z_ground[j, i]
            z_top = z_bot + litter_depth

            # Find matching z voxel indices
            k_mask = (z_coords >= z_bot) & (z_coords <= z_top)
            if not np.any(k_mask):
                # Ensure at least bottom voxel is filled if depth is small
                k_idx = int(np.clip((z_bot - z_min) / dz, 0, nz - 1))
                v_grid[k_idx, j, i] = density
            else:
                v_grid[k_mask, j, i] = density

    return v_grid


def voxels_3d_to_coordinate_array(
    v_grid: np.ndarray,
    domain_bounds: tuple[float, float, float, float, float, float],
    voxel_sizes: tuple[float, float, float],
) -> tuple[np.ndarray, np.ndarray]:
    """Converts a 3D voxel density array (nz, ny, nx) to non-empty (N, 3) center coordinates and (N,) bulk densities.

    Parameters
    ----------
    v_grid : np.ndarray
        3D voxel array of shape (nz, ny, nx).
    domain_bounds : tuple of float
        (x_min, y_min, z_min, x_max, y_max, z_max)
    voxel_sizes : tuple of float
        (dx, dy, dz) voxel dimensions.

    Returns
    -------
    coords : np.ndarray
        Array of shape (N, 3) containing (X, Y, Z) voxel center coordinates.
    bds : np.ndarray
        Array of shape (N,) containing corresponding bulk density values.
    """
    x_min, y_min, z_min, _x_max, _y_max, _z_max = domain_bounds
    dx, dy, dz = voxel_sizes

    k_indices, j_indices, i_indices = np.nonzero(v_grid > 0)

    if len(k_indices) == 0:
        return np.empty((0, 3), dtype=float), np.empty((0,), dtype=float)

    x_centers = x_min + (i_indices + 0.5) * dx
    y_centers = y_min + (j_indices + 0.5) * dy
    z_centers = z_min + (k_indices + 0.5) * dz

    coords = np.column_stack((x_centers, y_centers, z_centers))
    bds = v_grid[k_indices, j_indices, i_indices]

    return coords, bds


class BaseLitterModel(ABC):
    """Abstract Base Class for Ground Fuel Litter Models."""

    @abstractmethod
    def compute_litter_distribution(self, *args, **kwargs) -> np.ndarray:
        """Computes and returns the 2D spatial litter distribution grid."""
        pass


class TreeDistanceLitterModel(BaseLitterModel):
    """Model i: Distance-Decay Litter Accumulation from Tree Map Stems.

    Calculates ground litter bulk density (kg/m3) or mass load (kg/m2)
    as an exponential decay function of distance to surrounding tree trunks.
    """

    def __init__(
        self,
        tree_stems: np.ndarray,
        base_bulk_density: float = 15.0,
        min_bulk_density: float = 2.0,
        alpha: float = 0.5,
        max_radius: float | None = 10.0,
    ):
        """
        Parameters
        ----------
        tree_stems : np.ndarray
            Array of shape (N, 2) containing (X, Y) tree stem positions.
        base_bulk_density : float
            Peak bulk density near tree trunks (kg/m3).
        min_bulk_density : float
            Background / minimum bulk density far from trunks (kg/m3).
        alpha : float
            Characteristic spatial decay coefficient (1/m).
        max_radius : float, optional
            Maximum search radius for tree influence (m). If None, all trees contribute.
        """
        self.tree_stems = np.asarray(tree_stems)
        self.base_bd = base_bulk_density
        self.min_bd = min_bulk_density
        self.alpha = alpha
        self.max_radius = max_radius

    def compute_litter_distribution(
        self,
        grid_bounds: tuple[float, float, float, float],
        resolution: tuple[float, float],
    ) -> np.ndarray:
        """Computes the 2D spatial litter bulk density grid over a specified domain.

        Parameters
        ----------
        grid_bounds : tuple of float
            (x_min, y_min, x_max, y_max)
        resolution : tuple of float
            (dx, dy) cell dimensions in meters.

        Returns
        -------
        np.ndarray
            2D grid of shape (ny, nx) with local bulk density values (kg/m3).
        """
        x_min, y_min, x_max, y_max = grid_bounds
        dx, dy = resolution

        x_coords = np.arange(x_min + dx / 2, x_max, dx)
        y_coords = np.arange(y_min + dy / 2, y_max, dy)
        grid_x, grid_y = np.meshgrid(x_coords, y_coords)

        if len(self.tree_stems) == 0:
            return np.full(grid_x.shape, self.base_bd, dtype=float)

        # Sum exponential decay from all tree stems
        decay_sum = np.zeros_like(grid_x, dtype=float)
        for sx, sy in self.tree_stems:
            dist = np.sqrt((grid_x - sx) ** 2 + (grid_y - sy) ** 2)
            if self.max_radius is not None:
                mask = dist <= self.max_radius
                decay_sum[mask] += np.exp(-self.alpha * dist[mask])
            else:
                decay_sum += np.exp(-self.alpha * dist)

        # Scale by base density difference, reaching base_bd at trunk (d=0) and decaying to min_bd
        decay_factor = np.clip(decay_sum, 0.0, 1.0)
        bd_grid = self.min_bd + (self.base_bd - self.min_bd) * decay_factor
        return bd_grid


class CanopyTurnoverLitterModel(BaseLitterModel):
    """Model ii: Canopy Turnover & Fall Dispersion Litter Model.

    Computes litter accumulation by vertically integrating canopy fuel voxels
    with point-density weighted bulk density correction, turnover rates,
    and 2D Gaussian convolution dispersion.
    """

    def __init__(
        self,
        turnover_rate: float = 0.20,
        accumulation_time: float = 3.0,
        dispersion_sigma: float = 1.5,
    ):
        """
        Parameters
        ----------
        turnover_rate : float
            Annual foliage/branch turnover rate (fraction per year, e.g. 0.2 = 20%/yr).
        accumulation_time : float
            Number of years of litter accumulation (years).
        dispersion_sigma : float
            Standard deviation of the 2D Gaussian wind dispersion kernel (meters).
        """
        self.turnover_rate = turnover_rate
        self.accumulation_time = accumulation_time
        self.dispersion_sigma = dispersion_sigma

    @staticmethod
    def apply_point_density_correction(
        point_counts: np.ndarray,
        nominal_bd: float,
    ) -> np.ndarray:
        """Scales voxel bulk density proportionally by point count relative to non-empty mean (Pv / Pfl).

        Parameters
        ----------
        point_counts : np.ndarray
            3D array of point counts per voxel (shape: nz, ny, nx).
        nominal_bd : float
            Nominal bulk density for the fuel layer (kg/m3).

        Returns
        -------
        np.ndarray
            3D array of point-density corrected voxel bulk densities (kg/m3).
        """
        counts = np.asarray(point_counts, dtype=float)
        non_zero_mask = counts > 0

        if not np.any(non_zero_mask):
            return np.zeros_like(counts)

        mean_points_fl = np.mean(counts[non_zero_mask])
        corrected_bd = np.zeros_like(counts)
        corrected_bd[non_zero_mask] = nominal_bd * (
            counts[non_zero_mask] / mean_points_fl
        )
        return corrected_bd

    def compute_litter_distribution(
        self,
        voxel_point_counts: np.ndarray,
        voxel_sizes: tuple[float, float, float],
        nominal_canopy_bd: float = 1.5,
    ) -> np.ndarray:
        """Computes the 2D spatial litter mass load grid (kg/m2).

        Parameters
        ----------
        voxel_point_counts : np.ndarray
            3D voxel point count array of shape (nz, ny, nx).
        voxel_sizes : tuple of float
            (dx, dy, dz) voxel dimensions in meters.
        nominal_canopy_bd : float
            Nominal bulk density of overhead canopy layer (kg/m3).

        Returns
        -------
        np.ndarray
            2D grid of shape (ny, nx) containing local litter mass load (kg/m2).
        """
        dx, dy, dz = voxel_sizes

        # Step 1: Correct bulk density per voxel (Pv / Pfl)
        corrected_bd = self.apply_point_density_correction(
            voxel_point_counts, nominal_canopy_bd
        )

        # Step 2: Vertical integration along z-axis to get Canopy Fuel Load (CFL, kg/m2)
        cfl_grid = np.sum(corrected_bd * dz, axis=0)  # Shape (ny, nx)

        # Step 3: Apply turnover and accumulation time to get direct vertical drop load (kg/m2)
        direct_drop_load = cfl_grid * self.turnover_rate * self.accumulation_time

        # Step 4: Apply 2D Gaussian convolution dispersion
        if self.dispersion_sigma > 0:
            sigma_px_y = self.dispersion_sigma / dy
            sigma_px_x = self.dispersion_sigma / dx

            # Apply mass-preserving 2D Gaussian filter
            dispersed_load = gaussian_filter(
                direct_drop_load,
                sigma=(sigma_px_y, sigma_px_x),
                mode="nearest",
            )
            # Normalize to guarantee exact total mass conservation
            total_initial_mass = np.sum(direct_drop_load)
            total_dispersed_mass = np.sum(dispersed_load)

            if total_dispersed_mass > 0:
                dispersed_load *= total_initial_mass / total_dispersed_mass

            return dispersed_load
        else:
            return direct_drop_load


def build_litter_bfm_tiles(
    litter_2d: np.ndarray,
    domain_bounds: tuple[float, float, float, float, float, float],
    voxel_sizes: tuple[float, float, float],
    litter_depth: float = 0.05,
    litter_moisture: float = 0.10,
    sv_ratio: float = 6000.0,
    num_bins: int = 10,
    min_threshold: float = 0.01,
) -> tuple[list[dict], list[dict]]:
    """Converts a 2D spatial litter bulk density matrix (kg/m3) into binned 1D Boundary Fuel Model
    SURF definitions and contiguous ground VENT patches.

    Parameters
    ----------
    litter_2d : np.ndarray
        2D array of shape (ny, nx) containing bulk density (kg/m3) per ground cell.
    domain_bounds : tuple of float
        (x_min, y_min, z_min, x_max, y_max, z_max) domain bounds.
    voxel_sizes : tuple of float
        (dx, dy, dz) cell dimensions.
    litter_depth : float
        Litter layer thickness in meters.
    litter_moisture : float
        Litter moisture fraction (e.g. 0.10).
    sv_ratio : float
        Surface to volume ratio (1/m).
    num_bins : int
        Number of discrete bulk density bins for SURF grouping.
    min_threshold : float
        Minimum bulk density threshold to consider a cell active.

    Returns
    -------
    surfs : list of dict
        List of dicts defining SURF properties (surf_id, bd_val, thickness, moisture, sv_ratio).
    vents : list of dict
        List of dicts defining VENT bounding boxes [x1, x2, y1, y2, z_min, z_min] and surf_id.
    """
    ny, nx = litter_2d.shape
    x_min, y_min, z_min = domain_bounds[0], domain_bounds[1], domain_bounds[2]
    dx, dy, _ = voxel_sizes

    active_mask = litter_2d > min_threshold
    if not np.any(active_mask):
        return [], []

    min_val = float(np.min(litter_2d[active_mask]))
    max_val = float(np.max(litter_2d[active_mask]))

    if max_val - min_val < 1e-5 or num_bins <= 1:
        bin_indices = np.zeros_like(litter_2d, dtype=int)
        bin_indices[active_mask] = 1
        bin_means = {1: max_val}
    else:
        edges = np.linspace(min_val, max_val + 1e-6, num_bins + 1)
        bin_indices = np.digitize(litter_2d, edges)
        bin_indices[~active_mask] = 0

        bin_means = {}
        for b_idx in range(1, num_bins + 1):
            mask_b = bin_indices == b_idx
            if np.any(mask_b):
                bin_means[b_idx] = float(np.mean(litter_2d[mask_b]))

    surfs = []
    for b_idx, mean_bd in sorted(bin_means.items()):
        surfs.append(
            {
                "surf_id": f"Litter_Class_{b_idx}",
                "bd_val": mean_bd,
                "thickness": litter_depth,
                "moisture": litter_moisture,
                "sv_ratio": sv_ratio,
            }
        )

    vents = []
    for j in range(ny):
        y1 = y_min + (j * dy)
        y2 = y_min + ((j + 1) * dy)

        i = 0
        while i < nx:
            b_idx = bin_indices[j, i]
            if b_idx == 0:
                i += 1
                continue

            # Merge contiguous columns in row j with same b_idx
            start_i = i
            while i < nx and bin_indices[j, i] == b_idx:
                i += 1
            end_i = i

            x1 = x_min + (start_i * dx)
            x2 = x_min + (end_i * dx)

            vents.append(
                {
                    "xb": [x1, x2, y1, y2, z_min, z_min],
                    "surf_id": f"Litter_Class_{b_idx}",
                }
            )

    return surfs, vents


def write_esri_ascii(
    file_path: Path,
    data_2d: np.ndarray,
    xllcorner: float,
    yllcorner: float,
    cellsize: float,
    nodata: float = -9999.0,
) -> None:
    """Writes a 2D numpy array as a standard ESRI ASCII Raster Grid (.asc) for GIS tools."""
    ny, nx = data_2d.shape
    # ESRI ASCII grids write from top row (North / max Y) to bottom row (South / min Y)
    flipped_data = np.flipud(data_2d)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"ncols         {nx}\n")
        f.write(f"nrows         {ny}\n")
        f.write(f"xllcorner     {xllcorner:.6f}\n")
        f.write(f"yllcorner     {yllcorner:.6f}\n")
        f.write(f"cellsize      {cellsize:.6f}\n")
        f.write(f"NODATA_value  {nodata}\n")
        for row in flipped_data:
            line_str = " ".join(f"{val:.4f}" for val in row)
            f.write(line_str + "\n")


def generate_litter_heatmap(
    file_path: Path,
    data_2d: np.ndarray,
    crop_extent: list[float],
    voxel_size: float,
    title_label: str = "Litter Model",
    litter_depth: float = 0.05,
    tree_stems: np.ndarray | None = None,
    metric_type: str = "bulk_density",
) -> None:
    """Renders a styled TIFF/PNG spatial heatmap image of the 2D litter bulk density or fuel load, cropped to the forest footprint."""
    try:
        import matplotlib

        try:
            matplotlib.use("Agg")
        except Exception:
            pass
        import matplotlib.pyplot as plt

        fx_min, fx_max, fy_min, fy_max = crop_extent
        width_m = fx_max - fx_min
        height_m = fy_max - fy_min

        active_mask = data_2d > 0.0
        plot_data = np.where(active_mask, data_2d, np.nan)

        max_val = float(np.nanmax(data_2d)) if np.any(active_mask) else 0.0
        mean_val = (
            float(np.nanmean(data_2d[active_mask])) if np.any(active_mask) else 0.0
        )
        if metric_type == "fuel_load":
            total_mass = float(np.sum(data_2d) * (voxel_size**2))
            cbar_label = "Litter Fuel Load (kg/m²)"
            title_text = "Ground Litter Fuel Load Distribution"
            colormap = "YlOrBr"
            stat_name = "Fuel Load"
            unit_str = "kg/m²"
        else:
            total_mass = float(np.sum(data_2d) * (voxel_size**2) * litter_depth)
            cbar_label = "Litter Bulk Density (kg/m³)"
            title_text = "Ground Litter Bulk Density Distribution"
            colormap = "YlOrRd"
            stat_name = "Bulk Density"
            unit_str = "kg/m³"

        fig, ax = plt.subplots(figsize=(9.5, 7.5), dpi=300)

        # Light neutral background for non-fuel regions
        ax.set_facecolor("#f4f5f7")

        im = ax.imshow(
            plot_data,
            origin="lower",
            extent=crop_extent,
            cmap=colormap,
            aspect="equal",
            zorder=2,
        )

        cbar = fig.colorbar(im, ax=ax, shrink=0.85, pad=0.03)
        cbar.set_label(cbar_label, fontsize=11, fontweight="bold")
        cbar.ax.tick_params(labelsize=10)

        clean_title = title_label.replace("_", " ").title()
        ax.set_title(
            f"{title_text}\n({clean_title})",
            fontsize=13,
            fontweight="bold",
            pad=14,
        )
        ax.set_xlabel("X Position (m)", fontsize=11, fontweight="bold", labelpad=8)
        ax.set_ylabel("Y Position (m)", fontsize=11, fontweight="bold", labelpad=8)
        ax.tick_params(axis="both", which="major", labelsize=10)
        ax.grid(True, linestyle="--", alpha=0.4, zorder=3)

        # Draw tree stem overlay if tree positions are provided (e.g. Model 1)
        if tree_stems is not None and len(tree_stems) > 0:
            stems_arr = np.asarray(tree_stems)
            in_extent = (
                (stems_arr[:, 0] >= fx_min - voxel_size)
                & (stems_arr[:, 0] <= fx_max + voxel_size)
                & (stems_arr[:, 1] >= fy_min - voxel_size)
                & (stems_arr[:, 1] <= fy_max + voxel_size)
            )
            vis_stems = stems_arr[in_extent]
            if len(vis_stems) > 0:
                ax.scatter(
                    vis_stems[:, 0],
                    vis_stems[:, 1],
                    s=55,
                    facecolors="#2d6a4f",
                    edgecolors="#ffffff",
                    linewidth=1.4,
                    marker="o",
                    zorder=6,
                    label=f"Tree Stems (N={len(vis_stems)})",
                )
                ax.legend(loc="upper right", fontsize=9.0, framealpha=0.92)

        # Rich informational legend / metadata box (zorder=10 ensures top visibility)
        info_text = (
            f"Plot Extent: {width_m:.1f} m × {height_m:.1f} m\n"
            f"Pixel Resolution: Δx = Δy = {voxel_size:.2f} m\n"
            f"Max {stat_name}: {max_val:.2f} {unit_str}\n"
            f"Mean {stat_name}: {mean_val:.2f} {unit_str}\n"
            f"Litter Depth: {litter_depth*100.0:.1f} cm\n"
            f"Total Litter Mass: {total_mass:.2f} kg"
        )
        box_props = dict(
            boxstyle="round,pad=0.6",
            facecolor="white",
            alpha=0.92,
            edgecolor="#999999",
            linewidth=1.0,
        )
        ax.text(
            0.03,
            0.96,
            info_text,
            transform=ax.transAxes,
            fontsize=9.5,
            verticalalignment="top",
            bbox=box_props,
            family="sans-serif",
            zorder=10,
        )

        fig.tight_layout()
        fmt = file_path.suffix.lstrip(".").lower()
        if fmt == "tif":
            fmt = "tiff"
        fig.savefig(file_path, format=fmt, bbox_inches="tight")
        plt.close(fig)
        return
    except Exception as e:
        print(f"[Heatmap Warning] Could not render Matplotlib heatmap: {e}")

    # Fallback using PIL / Pillow image generation if matplotlib fails
    try:
        from PIL import Image

        max_val = float(np.max(data_2d)) if np.max(data_2d) > 0 else 1.0
        norm_data = (np.flipud(data_2d) / max_val * 255.0).astype(np.uint8)
        img = Image.fromarray(norm_data, mode="L")
        img.save(file_path)
    except Exception:
        pass


def export_litter_rasters(
    litter_2d: np.ndarray,
    litter_depth: float,
    domain_bounds: tuple[float, float, float, float, float, float] | list[float],
    voxel_size: float,
    output_dir: str | Path,
    forest_bounds: tuple[float, float, float, float, float, float]
    | list[float]
    | None = None,
    litter_mode: str = "litter",
    prefix: str = "litter",
    log_callback: Any = None,
    tree_stems: np.ndarray | None = None,
) -> dict[str, Path]:
    """Exports 2D ground fuel litter maps as TIFF (.tif), PNG (.png), and CSV (.csv) for both Bulk Density and Fuel Load, cropped strictly to the forest plot footprint."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ny, nx = litter_2d.shape

    # Determine cropping coordinates based on forest_bounds or active non-zero mask
    x_centers = domain_bounds[0] + (np.arange(nx) + 0.5) * voxel_size
    y_centers = domain_bounds[1] + (np.arange(ny) + 0.5) * voxel_size

    if forest_bounds is not None:
        mask_x = (x_centers >= forest_bounds[0] - 1e-4) & (
            x_centers <= forest_bounds[3] + 1e-4
        )
        mask_y = (y_centers >= forest_bounds[1] - 1e-4) & (
            y_centers <= forest_bounds[4] + 1e-4
        )
    else:
        active_y, active_x = np.where(litter_2d > 0)
        if len(active_x) > 0 and len(active_y) > 0:
            mask_x = (np.arange(nx) >= np.min(active_x)) & (
                np.arange(nx) <= np.max(active_x)
            )
            mask_y = (np.arange(ny) >= np.min(active_y)) & (
                np.arange(ny) <= np.max(active_y)
            )
        else:
            mask_x = np.ones(nx, dtype=bool)
            mask_y = np.ones(ny, dtype=bool)

    col_indices = np.where(mask_x)[0]
    row_indices = np.where(mask_y)[0]

    if len(col_indices) > 0 and len(row_indices) > 0:
        c_min, c_max = col_indices[0], col_indices[-1]
        r_min, r_max = row_indices[0], row_indices[-1]
        cropped_litter_2d = litter_2d[r_min : r_max + 1, c_min : c_max + 1]
        crop_extent = [
            x_centers[c_min] - voxel_size / 2.0,
            x_centers[c_max] + voxel_size / 2.0,
            y_centers[r_min] - voxel_size / 2.0,
            y_centers[r_max] + voxel_size / 2.0,
        ]
    else:
        cropped_litter_2d = litter_2d
        crop_extent = [
            domain_bounds[0],
            domain_bounds[3],
            domain_bounds[1],
            domain_bounds[4],
        ]

    fuel_load_2d = cropped_litter_2d * litter_depth

    exported_files = {}

    # 1. Bulk Density Rasters (.csv, .tif, .png)
    csv_bd_path = out_dir / f"{prefix}_bulk_density.csv"
    np.savetxt(csv_bd_path, cropped_litter_2d, delimiter=",", fmt="%.4f")
    exported_files["csv_bd"] = csv_bd_path

    tif_bd_path = out_dir / f"{prefix}_bulk_density.tif"
    generate_litter_heatmap(
        tif_bd_path,
        cropped_litter_2d,
        crop_extent,
        voxel_size,
        title_label=litter_mode,
        litter_depth=litter_depth,
        tree_stems=tree_stems,
        metric_type="bulk_density",
    )
    exported_files["tif_bd"] = tif_bd_path

    png_bd_path = out_dir / f"{prefix}_bulk_density.png"
    generate_litter_heatmap(
        png_bd_path,
        cropped_litter_2d,
        crop_extent,
        voxel_size,
        title_label=litter_mode,
        litter_depth=litter_depth,
        tree_stems=tree_stems,
        metric_type="bulk_density",
    )
    exported_files["png_bd"] = png_bd_path

    # 2. Fuel Load Rasters (.csv, .tif, .png)
    csv_load_path = out_dir / f"{prefix}_fuel_load.csv"
    np.savetxt(csv_load_path, fuel_load_2d, delimiter=",", fmt="%.4f")
    exported_files["csv_load"] = csv_load_path

    tif_load_path = out_dir / f"{prefix}_fuel_load.tif"
    generate_litter_heatmap(
        tif_load_path,
        fuel_load_2d,
        crop_extent,
        voxel_size,
        title_label=litter_mode,
        litter_depth=litter_depth,
        tree_stems=tree_stems,
        metric_type="fuel_load",
    )
    exported_files["tif_load"] = tif_load_path

    png_load_path = out_dir / f"{prefix}_fuel_load.png"
    generate_litter_heatmap(
        png_load_path,
        fuel_load_2d,
        crop_extent,
        voxel_size,
        title_label=litter_mode,
        litter_depth=litter_depth,
        tree_stems=tree_stems,
        metric_type="fuel_load",
    )
    exported_files["png_load"] = png_load_path

    if log_callback:
        log_callback(
            f"Exported ground litter rasters: {prefix}_bulk_density (.tif, .png, .csv), {prefix}_fuel_load (.tif, .png, .csv)"
        )

    return exported_files
