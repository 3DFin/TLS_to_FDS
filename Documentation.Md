# TLS_to_FDS: Technical Documentation and User Manual

**Software Version**: 1.0.0  
**Documentation Version**: 1.0.0  
**Date**: August 2026  
**License**: GNU General Public License v3.0 (GPL-3.0)  

---

## License and Disclaimer

> **DISCLAIMER & WARRANTY**  
> This program comes with **ABSOLUTELY NO WARRANTY**. This is free software, and you are welcome to redistribute it under certain conditions. To see the full license terms, please visit [https://www.gnu.org/licenses/gpl-3.0.html](https://www.gnu.org/licenses/gpl-3.0.html). The license agreement may also be consulted directly within the **About** tab inside **TLS_to_FDS**.

---

## Executive Summary

**TLS_to_FDS** is an open-source software framework and desktop Graphical User Interface (GUI) engineered to convert three-dimensional (3D) Terrestrial Laser Scanning (TLS) point clouds into fully formatted, physics-based Fire Dynamics Simulator (FDS) computational domains.

Numerical fire spread models such as FDS require spatially explicit, discretized representations of forest fuel beds (voxel matrices) along with thermodynamic, aerodynamic, and environmental boundary parameters. Manual creation of these inputs from raw or semantically classified remote sensing data is technically challenging, time-consuming, and prone to error.

TLS_to_FDS automates this workflow by providing:
1. **C-Accelerated Voxelization**: Fast spatial indexing and point-density-driven bulk density scaling ($\rho_v = \rho_{\text{nominal}} \cdot \frac{N_v}{\bar{N}_{\text{layer}}}$).
2. **Dynamic 1D Boundary Fuel Model (BFM) Litter Discretization**: Two decoupled scientific models (Stem Distance Decay and Canopy Turnover Integration with Gaussian Wind Dispersion) discretized into 1D BFM `&SURF` classes and contiguous 2D ground `&VENT` patch tiles.
3. **Atmospheric & Firebrand Physics**: Monin-Obukhov similarity boundary layer profiles, logarithmic wind development delays, dynamic ignition footprint generation, and Lagrangian ember transport with empirical char/ash material density overrides.
4. **Automated Multi-Mesh MPI Decomposition**: Optimized parallel domain partitioning, coarse sky mesh placement, and automatic diagnostic output setup (Rate of Spread trackers, multi-height slice planes, and restart checkpoints).

---

## Table of Contents

1. [General Use and Workflow](#1-general-use-and-workflow)
2. [Input Files and Point Cloud Processing](#2-input-files-and-point-cloud-processing)
3. [Fuel Settings](#3-fuel-settings)
   - [3.1 Vegetation Layer Parameters](#31-vegetation-layer-parameters)
   - [3.2 Ground Fuels (Litter and Duff)](#32-ground-fuels-litter-and-duff)
4. [Fire and Wind Settings](#4-fire-and-wind-settings)
   - [4.1 Simulation Timing and Wind Field](#41-simulation-timing-and-wind-field)
   - [4.2 Atmospheric Boundary Layer Physics](#42-atmospheric-boundary-layer-physics)
   - [4.3 Ignition Boundary Setup](#43-ignition-boundary-setup)
   - [4.4 Ember Transport and Firebrand Physics](#44-ember-transport-and-firebrand-physics)
5. [Spatial Settings](#5-spatial-settings)
   - [5.1 Domain Padding and Canopy Enclosure](#51-domain-padding-and-canopy-enclosure)
   - [5.2 Parallel Multi-Mesh MPI Subdivisions](#52-parallel-multi-mesh-mpi-subdivisions)
6. [Output Settings](#6-output-settings)
   - [6.1 Volumetric Slices and Boundary Output Files](#61-volumetric-slices-and-boundary-output-files)
   - [6.2 Rate of Spread (RoS) Tracking](#62-rate-of-spread-ros-tracking)
   - [6.3 Multi-Height Slice Planes](#63-multi-height-slice-planes)
   - [6.4 Simulation Restarts and Output Intervals](#64-simulation-restarts-and-output-intervals)
7. [Scientific References](#7-scientific-references)

---

## 1. General Use and Workflow

TLS_to_FDS features an intuitive desktop interface built with PySide6 (Qt6). The application follows a 7-step sequential workflow:

```
+-----------------------------------------------------------------------------------+
|                              TLS_to_FDS GUI WORKFLOW                              |
+-----------------------------------------------------------------------------------+
| 1. Select Input Directory  ---> Folder containing segmented .las / .laz files     |
| 2. Select Output Directory ---> Destination for .fds and .bdf binary outputs      |
| 3. Set Voxel Resolution    ---> e.g. dx = dy = dz = 0.25 m                         |
| 4. Select Forest Preset    ---> Biome default properties (Ponderosa, Oak, etc.)   |
| 5. Configure Fuel Layers   ---> Assign point cloud files to fuel classes          |
| 6. Set Wind & Ignition     ---> Speed, direction, ABL stability, ignition pattern  |
| 7. Generate FDS Domain     ---> Assembles .fds master file and .bdf matrices      |
+-----------------------------------------------------------------------------------+
```

### Core Project Parameters

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **Input Directory** | `line_input_dir` | *Empty* | Path to the directory containing pre-segmented or unsegmented point cloud files (`.las`, `.laz`, `.ply`, `.xyz`). |
| **Output Directory** | `line_output_dir` | *Empty* | Destination folder where the master FDS script (`.fds`) and binary Fortran voxel matrices (`.bdf`) are saved. |
| **Voxel Size** | `spin_voxel_size` | `0.25 m` | Orthogonal cell dimension ($\Delta x = \Delta y = \Delta z$) of the computational grid. Smaller voxels capture fine branch architecture but increase total cell count exponentially ($N \propto \Delta x^{-3}$). *(Ref: Mell et al., 2007; McGrattan et al., 2013)*. |
| **Forest Preset** | `combo_preset` | `Ponderosa Pine Summer` | Biome preset selector that automatically populates literature-derived combustion properties (Bulk Density, Moisture, Surface-to-Volume ratio, Element length, Drag) for each semantic vegetation layer. |

---

## 2. Input Files and Point Cloud Processing

TLS_to_FDS ingests 3D point cloud datasets containing spatial coordinates $(X, Y, Z)$ and optional classification values.

### Input Modes
1. **Pre-Segmented Files**: The input directory contains separate `.las`/`.laz` files corresponding to individual vegetation strata (e.g. `grass.las`, `shrubs.las`, `stems.las`, `canopy.las`).
2. **Deep Learning Fallback Segmentation**: For single, unclassified point cloud files, TLS_to_FDS incorporates an integrated deep learning semantic segmentation model based on the PointNet++ architecture *(Laino et al., 2025)*, automatically partitioning raw point clouds into ground, understory, stem, and canopy layers.

---

## 3. Fuel Settings

Fuel parameterization converts discrete point clouds into continuum porous media or surface boundary conditions in FDS.

### 3.1 Vegetation Layer Parameters

Each 3D vegetation layer in the fuel table is assigned physical, thermal, and aerodynamic properties:

| Parameter | GUI Name | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **Nominal Bulk Density** | `bd` | Layer dependent (0.5 – 25.0 kg/m³) | Dry fuel mass per unit volume ($\text{kg/m}^3$). Represents the overall bulk density of the vegetation stratum. *(Ref: Rothermel, 1972)*. |
| **Moisture Content** | `moisture` | Fraction (0.10 – 0.30) | Dry-weight moisture fraction $M_f = \frac{m_{\text{water}}}{m_{\text{dry}}}$. Controls latent heat of vaporization during thermal degradation. *(Ref: Van Wagner, 1977)*. |
| **Surface-to-Volume Ratio** | `sv_ratio` | 500 – 8000 m⁻¹ | Surface area per unit volume ($S/V = \frac{A}{V}$). Governs radiative absorption, pyrolytic gas evolution, and surface area exposed to oxygen. High $S/V$ (grass) ignites faster than low $S/V$ (stems). *(Ref: Catchpole & de Mestre, 1986)*. |
| **Particle Length** | `length` | 0.10 – 0.50 m | Characteristic element length ($L$). Used in FDS drag and radiative transfer formulations for cylindrical particles. |
| **Drag Coefficient** | `drag` | `2.8` | Aerodynamic drag coefficient ($C_d$) of porous vegetative obstacles. Extracted from wind tunnel experiments on vegetative canopies. *(Ref: Mell et al., 2007; FDS Tech Guide)*. |

#### Dynamic Point-Density Bulk Density Scaling
To preserve localized canopy gaps, dense foliage clusters, and individual tree crowns, TLS_to_FDS dynamically scales voxel bulk density $\rho_v$ proportional to local point count $N_v$:
$$\rho_v = \rho_{\text{nominal}} \cdot \left( \frac{N_v}{\bar{N}_{\text{layer}}} \right)$$
where $\bar{N}_{\text{layer}}$ is the mean point count across all non-empty voxels in that vegetation layer.

---

### 3.2 Ground Fuels (Litter and Duff)

Thin surface fuel beds (3 mm to 5 cm thickness) are modeled as **1D Boundary Fuel Models (BFM)** mapped to ground `&VENT` boundaries rather than full 3D voxels to eliminate artificial dilution of bulk density in large CFD grid cells.

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **Enable Litter Layer** | `check_litter_active` | `False` | Toggles inclusion of a ground litter layer. |
| **Litter Model Mode** | `combo_litter_mode` | `Uniform` | Chooses between `Uniform` (homogeneous load), `Model 1: Tree Distance` (stem decay), or `Model 2: Canopy Turnover` (vertical integration). |
| **Litter Depth** | `spin_litter_depth` | `0.05 m` | Physical thickness of the surface litter bed ($h$). *(Ref: Albini, 1976)*. |
| **Litter Bulk Density** | `spin_litter_bd` | `15.0 kg/m³` | Baseline dry bulk density of the ground fuel bed. |
| **Litter Moisture** | `spin_litter_moisture` | `0.10` (10%) | Surface fuel moisture fraction. |
| **Number of Litter Bins** | `spin_num_litter_bins` | `10` | Number of discrete bulk density classes used to bin continuous spatial litter density maps into FDS `&SURF` definitions (`Litter_Class_1` through `Litter_Class_N`) and row-merged `&VENT` patches. |
| **Tree Map Path** | `line_tree_map` | *Empty* | Path to CSV/TXT file containing $(X, Y)$ stem coordinates for Model 1. |
| **Radial Decay Rate ($\alpha$)** | `spin_decay_alpha` | `0.5` | Exponential decay coefficient in Model 1: $\rho(r) = \rho_{\text{min}} + (\rho_0 - \rho_{\text{min}}) e^{-\alpha r}$, controlling how rapidly litter density drops with distance $r$ from stems. |
| **Min Litter Bulk Density** | `spin_min_litter_bd` | `2.0 kg/m³` | Background litter bulk density far from tree trunks in Model 1. |
| **Canopy Turnover Rate** | `spin_turnover_rate` | `0.20` (20%/yr) | Annual foliage/branch drop fraction shed from overhead canopy in Model 2. *(Ref: Keane, 2015)*. |
| **Accumulation Time** | `spin_accumulation_years` | `3.0 years` | Years of unburned litter accumulation in Model 2. |
| **Dispersion Sigma ($\sigma$)** | `spin_dispersion_sigma` | `1.5 m` | Standard deviation (m) of the 2D Gaussian kernel modeling wind dispersion of falling canopy foliage. Guarantees mass conservation via normalization. *(Ref: Mell et al., 2026)*. |
| **DTM File Path** | `line_dtm_path` | *Empty* | Path to Digital Terrain Model point cloud or raster used for ground surface elevation referencing. |

---

## 4. Fire and Wind Settings

### 4.1 Simulation Timing and Wind Field

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **Total Simulation Time** | `spin_sim_time` | `240.0 s` | Total duration of the fire simulation in seconds. |
| **Wind Development Time** | `spin_wind_dev` | `25.0 s` | Pre-ignition stabilization period ($t_{\text{dev}}$). Allows atmospheric boundary layer wind profiles to stabilize and traverse the domain before fire ignition commences. *(Ref: Simó-Martí et al., 2026)*. |
| **Wind Direction** | `spin_wind_dir` | `270º` | Meteorological wind origin direction: 0º (North), 90º (East), 180º (South), 270º (West, flowing East). |
| **Wind Speed** | `spin_wind_speed` | `3.0 m/s` | Reference wind speed ($U_{\text{ref}}$) applied at domain boundaries. |

---

### 4.2 Atmospheric Boundary Layer Physics

The atmospheric boundary layer (ABL) velocity profile $u(z)$ is computed using Monin-Obukhov similarity theory:

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **Obukhov Length ($L$)** | `spin_obukhov` | `-500.0 m` | Characterizes lower atmospheric thermal stability. $L < 0$ denotes unstable convective conditions; $L > 0$ denotes stable conditions; $-500\text{ m}$ or $\infty$ represents neutral stratification. *(Ref: Monin & Obukhov, 1954; FDS User Guide)*. |
| **Aerodynamic Roughness ($z_0$)** | `spin_z0` | `0.5 m` | Ground roughness length defining the height where logarithmic wind speed drops to zero. Standard Davenport-Wieringa terrain values: `0.03 m` (open grass), `0.25 m` (scattered trees), `0.5 m` (forest stands), `1.0 m` (closed forests). *(Ref: Wieringa, 1992)*. |

---

### 4.3 Ignition Boundary Setup

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **HRRPUA** | `spin_hrrpua` | `2500.0 kW/m²` | Heat Release Rate Per Unit Area for the ignition burner. Provides thermal energy required to initiate fuel pyrolysis. *(Ref: Babrauskas, 1984; Mell et al., 2007)*. |
| **Ignition Duration** | `spin_ign_duration` | `10.0 s` | Time duration the artificial ignition line remains active before shutting off. |
| **Ignition Vent Width** | `spin_vent_width` | `1.0 m` | Physical width of the ignition vent strip along the domain boundary. |
| **Ignition Pattern** | `combo_ign_pattern` | `Line: South Edge (y_min)` | Geometric footprint of ignition: Line fires (South/North/East/West edges), Point ignition, or Perimeter polygon. Automatically snaps to vegetation outer bounds. |

---

### 4.4 Ember Transport and Firebrand Physics

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **Enable Ember Transport** | `check_track_embers` | `False` | Toggles Lagrangian firebrand particle generation. When active, TLS_to_FDS automatically applies empirical char density ($\rho_{\text{char}} = 180\text{ kg/m}^3$) and ash density ($\rho_{\text{ash}} = 50\text{ kg/m}^3$) material overrides. *(Ref: Mell et al., 2026)*. |
| **Ember Density Threshold** | `spin_ember_density` | `100.0 kg/m³` | Density threshold at which decaying vegetative particles convert into loftable char firebrands. |
| **Ember Velocity Threshold** | `spin_ember_velocity` | `2.0 m/s` | Critical localized updraft wind velocity required for aerodynamic lifting and firebrand breakaway into the plume flow. *(Ref: Manzello et al., 2008)*. |

---

## 5. Spatial Settings

### 5.1 Domain Padding and Canopy Enclosure

Computational domain boundaries must extend beyond the physical vegetation bounding box to prevent numerical boundary reflection and flow distortion:

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **X Domain Padding** | `spin_pad_x` | `10.0 m` | Lateral domain extension along the X axis. |
| **Y Domain Padding** | `spin_pad_y` | `10.0 m` | Inflow and outflow domain extension along the Y axis. |
| **Z Sky Padding** | `spin_pad_z` | `20.0 m` | Vertical height of coarse sky mesh placed above the forest canopy. TLS_to_FDS enforces the rule $Z_{\text{max}} \ge 5 \times H_{\text{canopy}}$ to prevent top boundary flow constriction. *(Ref: McGrattan et al., 2013)*. |
| **Domain Geometry Wizard** | `btn_domain_wizard` | *N/A* | Interactive tool that calculates optimal padding and multi-mesh grid dimensions based on target cell counts. |

---

### 5.2 Parallel Multi-Mesh MPI Subdivisions

FDS utilizes Message Passing Interface (MPI) for multi-core parallel processing:

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **MPI X Subdivisions** | `spin_mpi_x` | `2` | Number of mesh domain partitions along the X axis (`MPI_X`). |
| **MPI Y Subdivisions** | `spin_mpi_y` | `3` | Number of mesh domain partitions along the Y axis (`MPI_Y`). |

*Total Base Grid Meshes* = $\text{MPI}_X \times \text{MPI}_Y$ (e.g. $2 \times 3 = 6$ meshes, plus 1 coarse sky mesh = 7 parallel MPI processes).

---

## 6. Output Settings

### 6.1 Volumetric Slices and Boundary Output Files

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **HRRPUA (Boundary File)** | `check_out_hrrpua` | `True` | Exports 2D ground surface heat release rate maps (`&BNDF`). Essential for calculating Rate of Spread (RoS) and fireline intensity. |
| **Volumetric HRR (Slice)** | `check_out_flame` | `True` | Exports mid-plane 2D slices of volumetric heat release rate (`&SLCF` HRRPUV) to visualize 3D flame structure and flame height. |
| **Gas Temperature (Slice)** | `check_out_temp` | `True` | Exports mid-plane 2D gas temperature slices (`&SLCF`). Used for convective plume analysis and crown scorch modeling. |
| **Wind Velocity (Slice)** | `check_out_wind` | `True` | Exports 2D velocity vector slices (`&SLCF` U, W velocity) to analyze wind-fire coupling and fire-induced indrafts. |
| **Dry Biomass Tracking** | `check_out_biomass` | `False` | Tracks total dry fuel mass (kg) remaining in each vegetation stratum over time to determine percentage fuel consumption. |

---

### 6.2 Rate of Spread (RoS) Tracking

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **Enable RoS Trackers** | `check_ros_tracking` | `False` | Generates 4 transverse device lines (`&DEVC`) measuring `MAXLOC X` or `MAXLOC Y` temperature statistics across domain span transects (at 20%, 40%, 60%, and 80% span). Automatically logs fire front arrival times across the plot. |

---

### 6.3 Multi-Height Slice Planes

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **Slice Heights (m)** | `line_slice_heights` | `"1.0"` | Comma-separated list of horizontal elevation planes (e.g. `0.5, 1.5, 2.5`) for multi-level `&SLCF` slice outputs. Enables vertical profiling of plume temperatures and horizontal wind speeds through the canopy. |

---

### 6.4 Simulation Restarts and Output Intervals

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **Enable Simulation Restarts** | `check_restart_active` | `False` | Activates FDS restart checkpoint dumps (`&DUMP DT_RESTART`) allowing long runs to be paused, resumed, or recovered after cluster job timeouts. |
| **Restart Interval** | `spin_dt_restart` | `25.0 s` | Time interval in seconds between restart checkpoint saves. |
| **HRR Output Interval** | `spin_dt_hrr` | `0.1 s` | Time interval for writing global Heat Release Rate diagnostic curves. |
| **Device Output Interval** | `spin_dt_devc` | `0.1 s` | Time interval for logging device (`&DEVC`) time series data. |
| **Particle Output Interval** | `spin_dt_part` | `0.1 s` | Time interval for exporting Lagrangian ember particle tracking visualization files. |

---

## 7. Scientific References

* **Albini, F.A. (1976)**. *Estimating wildfire behavior and effects*. USDA Forest Service General Technical Report INT-30, Intermountain Forest and Range Experiment Station, Ogden, Utah.
* **Babrauskas, V. (1984)**. Development of the cone calorimeter—A bench-scale heat release rate apparatus based on oxygen consumption. *Fire and Materials*, 8(2), 81–95.
* **Catchpole, E.A., & de Mestre, A.J. (1986)**. Physical properties of forest fuels. *Australian Forestry*, 49(2), 106–111.
* **Keane, R.E. (2015)**. *Wildland fuel fundamentals and applications*. Springer Earth System Sciences, New York.
* **Laino, D., et al. (2025)**. Semantic segmentation of terrestrial point clouds for wildland fuel characterization. *Remote Sensing of Environment*, 302, 113940.
* **Manzello, S.L., et al. (2008)**. On the characterize of embers generated from burning trees. *International Journal of Wildland Fire*, 17(2), 223–234.
* **McGrattan, K., et al. (2013)**. *Fire Dynamics Simulator User's Guide*. NIST Special Publication 1019, National Institute of Standards and Technology, Gaithersburg, Maryland.
* **Mell, W., et al. (2007)**. A physics-based approach to modelling wildland fire spread. *International Journal of Wildland Fire*, 16(1), 1–22.
* **Mell, W., et al. (2026)**. Fire Dynamics Simulator and QUIC-fire simulations of the 2014 Camp Swift experiments. *International Journal of Wildland Fire*, 35, WF25104.
* **Monin, A.S., & Obukhov, A.M. (1954)**. Basic laws of turbulent mixing in the surface layer of the atmosphere. *Trudy Geofizicheskogo Instituta Akademiya Nauk SSSR*, 24(151), 163–187.
* **Rothermel, R.C. (1972)**. *A mathematical model for predicting fire spread in wildland fuels*. USDA Forest Service Research Paper INT-115, Ogden, Utah.
* **Simó-Martí, et al. (2026)**. Wind stabilization and boundary layer development in computational fire simulations. *Journal of Wind Engineering and Industrial Aerodynamics* (under review).
* **Van Wagner, C.E. (1977)**. Conditions for start and spread of crown fire. *Canadian Journal of Forest Research*, 7(1), 23–34.
* **Wieringa, J. (1992)**. Updating the Davenport roughness classification for landscape terrain. *Journal of Wind Engineering and Industrial Aerodynamics*, 41(1-3), 357–368.
