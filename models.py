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

@dataclass
class OutputParams:
    hrrpua: bool
    flame: bool
    temp: bool
    wind: bool
    biomass: bool

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