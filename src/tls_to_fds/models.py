"""Configuration Dataclasses for TLS_to_FDS.

Defines typed dataclasses for environmental parameters, ground fuels, diagnostic output controls,
domain decomposition, and the unified runtime pipeline configuration.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class EnvParams:
    """Atmospheric, wind, ignition, and firebrand ember tracking parameters."""

    sim_time: float
    wind_dev_time: float
    wind_dir: float
    wind_speed: float
    hrrpua: float
    track_embers: bool
    ign_duration: float
    obukhov: float
    z0: float
    ember_density: float
    ember_velocity: float
    ign_pattern: str
    vent_width: float
    ros_tracking: bool = False


@dataclass
class GroundFuels:
    """Surface ground fuel (litter/duff) physical properties and accumulation model parameters."""

    litter_active: bool
    litter_depth: float
    litter_bd: float
    litter_moisture: float
    # Dynamic litter model configuration
    litter_model_mode: str = "Uniform"  # Options: "Uniform", "Model 1: Tree Distance", "Model 2: Canopy Turnover"
    tree_map_path: str = ""
    dtm_path: str = ""
    decay_alpha: float = 0.5
    min_litter_bd: float = 2.0
    turnover_rate: float = 0.20
    accumulation_years: float = 3.0
    dispersion_sigma: float = 1.5
    num_litter_bins: int = 10


@dataclass
class OutputParams:
    """Diagnostic slice planes, boundary heat release maps, and checkpoint timing parameters."""

    hrrpua: bool
    flame: bool
    temp: bool
    wind: bool
    biomass: bool
    restart_active: bool = False
    dt_restart: float = 25.0
    dt_hrr: float = 0.1
    dt_devc: float = 0.1
    dt_part: float = 0.1
    slice_heights: str = "1.0"


@dataclass
class DomainParams:
    """Computational domain buffer padding, sky mesh coarsening, and MPI partition counts."""

    lateral_pad: float
    top_pad: float
    sky_multiplier: int
    mpi_x: int
    mpi_y: int


@dataclass
class RuntimeConfig:
    """Unified runtime configuration passed from the GUI to the execution pipeline."""

    input_directory: str
    output_directory: str
    output_filename: str
    preset_name: str
    voxel_size: float
    fuel_layers: list[dict[str, Any]]
    env_params: EnvParams
    ground_fuels: GroundFuels
    output_params: OutputParams
    domain_params: DomainParams
