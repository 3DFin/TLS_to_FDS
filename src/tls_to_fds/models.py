from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class EnvParams:
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


@dataclass
class GroundFuels:
    litter_active: bool
    litter_depth: float
    litter_bd: float
    litter_moisture: float
    duff_active: bool
    duff_depth: float
    duff_bd: float
    duff_moisture: float
    # Dynamic litter model configuration
    litter_model_mode: str = "Uniform"  # Options: "Uniform", "Model 1: Tree Distance", "Model 2: Canopy Turnover"
    tree_map_path: str = ""
    decay_alpha: float = 0.5
    min_litter_bd: float = 2.0
    turnover_rate: float = 0.20
    accumulation_years: float = 3.0
    dispersion_sigma: float = 1.5


@dataclass
class OutputParams:
    hrrpua: bool
    flame: bool
    temp: bool
    wind: bool
    biomass: bool


@dataclass
class DomainParams:
    lateral_pad: float
    top_pad: float
    sky_multiplier: int
    mpi_x: int
    mpi_y: int


@dataclass
class RuntimeConfig:
    input_directory: str
    output_directory: str
    output_filename: str
    preset_name: str
    voxel_size: float
    fuel_layers: List[Dict[str, Any]]
    env_params: EnvParams
    ground_fuels: GroundFuels
    output_params: OutputParams
    domain_params: DomainParams
