"""Dynamic Ground Fuel Litter Accumulation Models.

Provides decoupled scientific models for computing 2D spatial distributions
of ground fuel (litter/duff) load and bulk density:
- Model i (TreeDistanceLitterModel): Tree map distance-decay function.
- Model ii (CanopyTurnoverLitterModel): Vertical canopy integration with point-density
  weighted bulk density scaling and 2D Gaussian dispersion convolution.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple, Union, Optional
import numpy as np
from scipy.ndimage import gaussian_filter


def load_tree_map(file_path: Union[str, Path]) -> np.ndarray:
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

    elif suffix in [".csv", ".txt"]:
        # Try reading with pandas or numpy
        try:
            data = np.genfromtxt(path, delimiter=",", names=True)
            names = [n.lower() for n in data.dtype.names] if data.dtype.names else []
            if "x" in names and "y" in names:
                return np.vstack((data["x"], data["y"])).T
        except Exception:
            pass

        # Fallback to plain numpy text load ignoring headers
        raw = np.loadtxt(
            path, delimiter="," if "," in path.read_text()[:500] else None, skiprows=1
        )
        if raw.ndim == 1:
            raw = raw.reshape(1, -1)
        return raw[:, :2]

    else:
        raise ValueError(f"Unsupported tree map file extension: {suffix}")


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
        max_radius: Optional[float] = 10.0,
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
        grid_bounds: Tuple[float, float, float, float],
        resolution: Tuple[float, float],
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

        bd_grid = np.full(grid_x.shape, self.min_bd, dtype=float)

        if len(self.tree_stems) == 0:
            return bd_grid

        # Sum exponential decay from all tree stems
        decay_sum = np.zeros_like(grid_x, dtype=float)
        for sx, sy in self.tree_stems:
            dist = np.sqrt((grid_x - sx) ** 2 + (grid_y - sy) ** 2)
            if self.max_radius is not None:
                mask = dist <= self.max_radius
                decay_sum[mask] += np.exp(-self.alpha * dist[mask])
            else:
                decay_sum += np.exp(-self.alpha * dist)

        # Scale by base density difference, capped at peak base_bd
        bd_grid += (self.base_bd - self.min_bd) * (1.0 - np.exp(-decay_sum))
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
        voxel_sizes: Tuple[float, float, float],
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
