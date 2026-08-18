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

## Summary

**TLS_to_FDS** is an open-source software framework and desktop Graphical User Interface (GUI) engineered to convert three-dimensional (3D) Terrestrial Laser Scanning (TLS) point clouds into fully formatted, physics-based Fire Dynamics Simulator (FDS) computational domains.

Numerical fire spread models such as FDS require spatially explicit, discretized representations of forest fuel beds (voxel matrices) along with thermodynamic, aerodynamic, and environmental boundary parameters. Manual creation of these inputs from raw or semantically classified remote sensing data is technically challenging, time-consuming, and prone to error.

TLS_to_FDS automates this workflow by providing:
1. **C-Accelerated Voxelization**: Fast spatial indexing and point-density-driven bulk density scaling.
2. **Dynamic 1D Boundary Fuel Model (BFM) Litter Discretization**: Two decoupled scientific models (Stem Distance Decay and Canopy Turnover Integration with Gaussian Wind Dispersion) discretized into 1D BFM `&SURF` classes and contiguous 2D ground `&VENT` patch tiles.
3. **Atmospheric & Firebrand Physics**: Atmosphere and wind field setup, dynamic ignition footprint generation, and Lagrangian ember transport with empirical char/ash material density overrides.
4. **Automated Multi-Mesh MPI Decomposition**: Parallel domain partitioning, coarse sky mesh placement, and automatic diagnostic output setup (Rate of Spread trackers, multi-height slice planes, and restart checkpoints).
5. **Vectorized BDF Binary Exporter**: High-performance structured Fortran Binary Data (`.bdf`) file generator.

---

## Table of Contents

1. [General Use and Workflow](#1-general-use-and-workflow)
2. [Input Files and Point Cloud Processing](#2-input-files-and-point-cloud-processing)
3. [Fuel Settings](#3-fuel-settings)
   - [3.1 Vegetation Layer Parameters](#31-vegetation-layer-parameters)
   - [3.2 Ground Fuels (Litter and Duff)](#32-ground-fuels-litter-and-duff)
4. [Fire and Wind Settings](#4-fire-and-wind-settings)
   - [4.1 Wind Field & Atmospheric Forcing](#41-wind-field--atmospheric-forcing)
   - [4.2 Atmospheric Boundary Layer Physics](#42-atmospheric-boundary-layer-physics)
   - [4.3 Ignition Boundary Setup](#43-ignition-boundary-setup)
   - [4.4 Ember Transport and Firebrand Physics](#44-ember-transport-and-firebrand-physics)
5. [Spatial Settings](#5-spatial-settings)
   - [5.1 Domain Padding and Canopy Enclosure](#51-domain-padding-and-canopy-enclosure)
   - [5.2 Parallel Multi-Mesh MPI Subdivisions](#52-parallel-multi-mesh-mpi-subdivisions)
6. [Output Settings & Diagnostics](#6-output-settings--diagnostics)
   - [6.1 Simulation Timing and Volumetric Outputs](#61-simulation-timing-and-volumetric-outputs)
   - [6.2 Rate of Spread (RoS) Tracking](#62-rate-of-spread-ros-tracking)
   - [6.3 Multi-Height Slice Planes](#63-multi-height-slice-planes)
   - [6.4 Simulation Restarts and Output Intervals](#64-simulation-restarts-and-output-intervals)
   - [6.5 Interactive 3D Pre-Simulation Scene Visualization](#65-interactive-3d-pre-simulation-scene-visualization)
7. [Scientific References](#7-scientific-references)
8. [Appendix A: Forest Biome Presets Reference](#8-appendix-a-forest-biome-presets-reference)
9. [Appendix B: Generated Output Files Summary](#9-appendix-b-generated-output-files-summary)

---

## 1. General Use and Workflow

TLS_to_FDS features an intuitive desktop interface built with PySide6 (Qt6). The application follows a 7-step sequential workflow:

```
+-----------------------------------------------------------------------------------+
|                              TLS_to_FDS GUI WORKFLOW                              |
+-----------------------------------------------------------------------------------+
| 1. Select Input Directory  ---> Folder containing segmented .las / .laz files     |
| 2. Select Output Directory ---> Destination for .fds and .bdf binary outputs      |
| 3. Select Forest Preset    ---> Biome default properties (Ponderosa, Oak, etc.)   |
| 4. Configure Fuel Layers   ---> Assign point cloud files to fuel classes          |
| 5. Set Spatial & Mesh      ---> Resolution (dx), domain padding, MPI partitions   |
| 6. Set Wind & Ignition     ---> Speed, direction, ABL stability, ignition pattern |
| 7. Generate FDS Domain     ---> Assembles .fds master file and .bdf matrices      |
+-----------------------------------------------------------------------------------+
```

### Core Project Parameters

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **Input Directory** | `line_input_dir` | *Empty* | Path to the directory containing pre-segmented or unsegmented point cloud files (`.las`, `.laz`, `.ply`, `.xyz`). |
| **Output Directory** | `line_output_dir` | *Empty* | Destination folder where the master FDS script (`.fds`) and binary Fortran voxel matrices (`.bdf`) are saved. |
| **Forest Preset** | `combo_preset` | `Ponderosa Pine Summer` | Biome preset selector that automatically populates literature-derived combustion properties (Bulk Density, Moisture, Surface-to-Volume ratio, Element length, Drag) for each semantic vegetation layer. |

---

## 2. Input Files and Point Cloud Processing

TLS_to_FDS ingests 3D point cloud datasets containing spatial coordinates $(X, Y, Z)$ and optional classification values.

### Input Modes
1. **Pre-Segmented Files**: The input directory contains separate `.las`/`.laz` files corresponding to individual vegetation strata (e.g. `grass.las`, `shrubs.las`, `stems.las`, `canopy.las`).
2. **UPCOMING: Deep Learning Fallback Segmentation**: For single, unclassified point cloud files, TLS_to_FDS will incorporate an integrated deep learning semantic segmentation model based on the Point Transformer V3 architecture *(Wu et al., 2023)*, automatically partitioning raw point clouds into ground, understory, stem, and canopy layers.

---

## 3. Fuel Settings

Wildland fuels are heterogeneous, porous media whose physical and thermal characteristics dictate ignition probability, pyrolytic gas evolution, and fire spread. TLS_to_FDS converts 3D discrete point clouds into continuum porous media and surface boundary conditions in FDS by explicitly parameterizing fundamental **fuel properties**:

1. **Fuel Composition & Organic Content**: Chemical makeup (cellulose, hemicellulose, lignin) and dry organic mass vs. non-combustible mineral ash content, specified via FDS material definitions (`MATL_ID`).
2. **Moisture Content**: Dry-weight fuel moisture fraction ($M_f = m_{\text{water}}/m_{\text{dry}}$), dictating the thermal energy absorbed as latent heat during water vaporization prior to pyrolysis.
3. **Bulk Density**: Dry fuel mass per unit volume ($\rho_b$, $\text{kg/m}^3$), defining the dry combustible mass packed into each 3D vegetative voxel or ground boundary fuel cell.
4. **Fuel-Element Size & Shape**: Characteristic particle length ($L$, $\text{m}$) and **fuel-element shape (characterized by surface-to-volume ratio, $S/V = A/V$, $\text{m}^{-1}$)**. High $S/V$ fine fuels (grasses, foliage) exhibit rapid radiative absorption and fast surface pyrolysis, whereas low $S/V$ coarse fuels (stems, trunks) burn slower with sustained charring.
5. **Porosity & Packing Ratio**: Derived aerodynamic indicators calculated directly from voxel bulk density ($\beta = \rho_b / \rho_p$ and void fraction $\phi = 1 - \beta$, assuming solid particle density $\rho_p \approx 500\text{ kg/m}^3$), governing oxygen entrainment into the fuel bed, radiative attenuation, and drag.
6. **Unevenness in Fuel Distribution & Spatial Continuity**: Intra-canopy spatial heterogeneity, localized gaps, stem-centered decay gradients, and vertical/horizontal **continuity of fuel elements** (e.g., ladder fuel bridges connecting surface beds to overhead crowns).

### 3.1 Vegetation Layer Parameters

Individual 3D point cloud strata (e.g., surface fuels, canopy fuels, tree stems) are loaded into the interactive **Fuel Layers Table** in the GUI. When a fuel class is assigned to a layer, its physical, thermal, and aerodynamic combustion properties are automatically populated from the selected **Forest Preset** JSON configuration file (e.g., *Ponderosa Pine Summer*, *European Mixed Forest*, etc.). Users can also manually customize or override any of these values directly in the table:

| Parameter | GUI Name | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **Nominal Bulk Density** | `bd` | Layer dependent (0.5 – 25.0 kg/m³) | Dry fuel mass per unit volume ($\text{kg/m}^3$). Represents overall bulk density and packing ratio ($\beta = \rho_b / \rho_p$) of the fuel layers. *(Ref: Rothermel, 1972)*. |
| **Moisture Content** | `moisture` | Fraction (0.10 – 0.30) | Dry-weight moisture fraction $M_f = \frac{m_{\text{water}}}{m_{\text{dry}}}$. Controls latent heat of vaporization during thermal degradation. *(Ref: Van Wagner, 1977)*. |
| **Surface-to-Volume Ratio** | `sv_ratio` | 500 – 8000 m⁻¹ | Governs **fuel-element shape (characterized by surface to volume ratio, $S/V = A/V$)**. Controls radiative absorption, pyrolytic gas evolution, and surface area exposed to oxygen. High $S/V$ (grass) ignites faster than low $S/V$ (stems). *(Ref: Catchpole & de Mestre, 1986)*. |
| **Particle Length** | `length` | 0.10 – 0.50 m | Characteristic **fuel-element size** ($L$). Used in FDS drag and radiative transfer formulations for particles. |
| **Drag Coefficient** | `drag` | `2.8` | Aerodynamic drag coefficient ($C_d$) of porous vegetative obstacles. Governed by fuel porosity, fuel-element shape and particle length. *(Ref: Mell et al., 2007; FDS Tech Guide)*. |
| **Dynamic BD** | `dynamic_bd` | `True` | Toggles 2-stage micro-voxelization dynamic bulk density imputation. Captures the **unevenness in fuel distribution** and spatial **continuity of fuel elements** based on local micro-voxel occupancy ($1\text{ cm}$) while preserving total dry fuel mass. |

#### 2-Stage Micro-Voxelization Dynamic Bulk Density Imputation
To capture intra-canopy foliage clustering, gaps, and crown architecture while eliminating point-density bias from multi-scan coregistration overlaps, beam divergence, and range attenuation, TLS_to_FDS implements a **2-stage micro-voxelization algorithm**:

1. **Stage 1 (1 cm Micro-Voxelization)**: The raw 3D point cloud of the vegetation layer is pre-voxelized at a fine sub-voxel resolution ($\text{sub\_voxel\_size} = 0.01\text{ m} = 1\text{ cm}$) using C-accelerated spatial hashing (`dendroptimized`). This collapses redundant or overlapping LiDAR returns occurring within the same $1\text{ cm}^3$ spatial volume into a single active micro-voxel center coordinate, decoupling point counts from multi-scan alignment inflation.
2. **Stage 2 (Simulation Voxelization & Occupancy Count $P_v$)**: The unique 1 cm micro-voxel centers are then voxelized at the target simulation grid resolution ($\Delta x = \text{voxel\_size}$, e.g. $0.25\text{ m}$). The number of occupied 1 cm micro-voxels within simulation voxel $v$ is recorded as $P_v$.
3. **Stage 3 (Mean Occupancy & Density Correction)**: The mean micro-voxel occupancy across all non-empty simulation voxels in that fuel layer ($N_{fl}$) is computed:
   $$\bar{P}_{fl} = \frac{1}{N_{fl}} \sum_{v=1}^{N_{fl}} P_v$$
   The unconstrained voxel bulk density is scaled proportionally:
   $$\text{BD}_v^{\text{raw}} = \text{BD}_{\text{nominal}} \cdot \left( \frac{P_v}{\bar{P}_{fl}} \right)$$
4. **Stage 4 (Safety Bounds & Mass Preservation)**: To prevent extreme density spikes from scan artifacts or sparse outliers, safety ratio bounds are applied:
   $$\text{BD}_v^{\text{clamped}} = \max\left( 0.05 \cdot \text{BD}_{\text{nominal}}, \, \min\left( 4.0 \cdot \text{BD}_{\text{nominal}}, \, \text{BD}_v^{\text{raw}} \right) \right)$$
   Finally, the bulk density values are re-normalized to guarantee exact preservation of total dry fuel mass ($\sum \text{BD}_v \cdot V_{\text{voxel}} = M_{\text{nominal}}$):
   $$\text{BD}_v = \text{BD}_v^{\text{clamped}} \cdot \left( \frac{N_{fl} \cdot \text{BD}_{\text{nominal}}}{\sum_{v=1}^{N_{fl}} \text{BD}_v^{\text{clamped}}} \right)$$

#### Vectorized Fortran Binary Data Format (.bdf) Export Architecture
In FDS, vegetative fuel matrices are read as unformatted Fortran sequential binary streams (`.bdf`). Each file contains:
1. **Header Records**:
   - **Record 1 (48 bytes)**: Computational bounding box $[X_{\text{min}}, X_{\text{max}}, Y_{\text{min}}, Y_{\text{max}}, Z_{\text{min}}, Z_{\text{max}}]$ as 6 double-precision floats (`float64`).
   - **Record 2 (24 bytes)**: Voxel cell dimensions $[\Delta x, \Delta y, \Delta z]$ as 3 double-precision floats (`float64`).
   - **Record 3 (4 bytes)**: Total active voxel count $N$ as a 32-bit integer (`int32`).
2. **Body Records (Per-Voxel Stream)**:
   - **Record $2i + 4$ (24 bytes)**: Voxel centroid coordinate vector $(x_i, y_i, z_i)$ (`float64`).
   - **Record $2i + 5$ (8 bytes)**: Local bulk density $\rho_i$ (`float64`).

Standard Fortran unformatted I/O wraps each logical record with 4-byte unsigned integer markers (`uint32`) denoting the record's byte length. In naive implementations, writing $N = 500,000$ voxels via per-element Python loops requires $1,000,000$ individual function calls, $1,000,000$ transient NumPy allocations, and hundreds of thousands of individual filesystem writes (taking $\approx 45$ seconds).

TLS_to_FDS eliminates this bottleneck using a **Zero-Copy Structured NumPy Interleaving Architecture**:
```python
dtype_voxel = np.dtype([
    ("tag_c1", "<u4"),       # 24 (4 bytes)
    ("coords", "<f8", (3,)),  # (X, Y, Z) centroid (24 bytes)
    ("tag_c2", "<u4"),       # 24 (4 bytes)
    ("tag_b1", "<u4"),       # 8 (4 bytes)
    ("bd", "<f8"),            # Bulk density (8 bytes)
    ("tag_b2", "<u4"),       # 8 (4 bytes)
])
```
The entire per-voxel payload ($48\text{ bytes/voxel}$) is generated in contiguous memory using vectorized array assignments and flushed to disk in **a single system write operation (`f.write()`)**. This achieves a **$\approx 1,000\times$ speedup** (sub-50 ms for 500,000+ voxels) with **100% byte-for-byte Fortran binary compliance**.

---

### 3.2 Ground Fuels (Litter and Duff)

#### Definitions & Physical Characteristics
- **Surface Litter Bed**: The upper, un-compacted ground fuel layer consisting of freshly deposited dead plant material, including conifer needles, broadleaf foliage, twigs, small branches ($\le 6\text{ mm}$ diameter), and reproductive structures (cones, seed pods). Litter beds are physically characterized by high porosity, low dry bulk density ($\rho_{\text{litter}} \approx 10 - 25\text{ kg/m}^3$), high surface-to-volume ratio ($S/V \approx 4000 - 9000\text{ m}^{-1}$), and rapid moisture exchange with atmospheric relative humidity.
- **FUTURE UPDATE: Duff Bed**: The underlying organic layer extending from the base of the litter bed down to mineral soil, composed of partially decomposed (fermentation layer) and highly decomposed (humus layer) organic material. Duff beds are characterized by higher bulk density ($\rho_{\text{duff}} \approx 40 - 150\text{ kg/m}^3$), lower $S/V$ ratio, high mineral ash content, and high water holding capacity.

#### Numerical Representation: 1D Boundary Fuel Model (BFM) Grid Tiles
Modeling thin surface fuel beds ($h \approx 0.01 - 0.05\text{ m}$) directly in 3D CFD grids ($\Delta z \approx 0.25 - 0.50\text{ m}$) creates severe numerical dilution: assigning a 5 cm litter bed of $15\text{ kg/m}^3$ to a 50 cm voxel reduces effective 3D bulk density tenfold ($\rho_{\text{3D}} = 1.5\text{ kg/m}^3$), causing under-predicted surface flame spread and artificial extinction.

TLS_to_FDS solves this by representing ground fuels as **1D Boundary Fuel Models (BFM)** mapped to 2D `&VENT` surface patches on the ground mesh boundary (`Z = 0`), utilizing multi-layer solid heat conduction and pyrolysis kinetics (`&SURF MATL_ID(1:2, 1)` with `GENERIC VEGETATION` over `SOIL`).

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

#### Scientific Ground Fuel Accumulation Models

##### 1. Uniform Litter Model
Applies a homogeneous bulk density ($\rho_{\text{litter}}$) and thickness ($h$) across the entire forest ground plane. Recommended for open grasslands, shrublands, or uniform plantation stands where spatial litter variations are negligible.

##### 2. Model 1: Tree Distance Decay Model
Models localized litter accumulation concentrated around tree trunks due to needle cast, branch fall, and bark shedding. Bulk density $\rho(x,y)$ decays exponentially as a function of Euclidean distance $d_k(x,y) = \sqrt{(x - x_k)^2 + (y - y_k)^2}$ to all tree stem locations $(x_k, y_k)$:
$$\rho(x,y) = \rho_{\text{min}} + (\rho_0 - \rho_{\text{min}}) \cdot \left[ 1 - \exp\left( -\sum_{k=1}^{N_{\text{stems}}} e^{-\alpha d_k(x,y)} \right) \right]$$
where $\rho_0$ is the peak nominal litter bulk density near tree stem locations (`spin_litter_bd`, e.g. $15.0\text{ kg/m}^3$), $\rho_{\text{min}}$ is the background inter-stem litter bulk density far from tree trunks (`spin_min_litter_bd`, e.g. $2.0\text{ kg/m}^3$), and $\alpha$ is the radial spatial decay coefficient ($1/\text{m}$).

##### 3. Model 2: Canopy Turnover & Fall Dispersion Model
Calculates spatially explicit litter mass load ($W_{\text{litter}}$, $\text{kg/m}^2$) directly from overhead 3D canopy LiDAR point clouds:
1. **Vertical Canopy Integration**: Integrates point-density corrected voxel bulk densities vertically to compute Canopy Fuel Load ($\text{CFL}$, $\text{kg/m}^2$):
   $$\text{CFL}(x,y) = \sum_{k=1}^{N_z} \rho_{\text{canopy}}(x,y,z_k) \cdot \Delta z$$
2. **Turnover Accumulation**: Applies annual foliage/twig turnover rate ($k_{\text{turnover}}$, $\text{yr}^{-1}$) and accumulation time ($T_{\text{accum}}$, $\text{years}$):
   $$W_{\text{direct}}(x,y) = \text{CFL}(x,y) \cdot k_{\text{turnover}} \cdot T_{\text{accum}}$$
3. **2D Gaussian Wind Dispersion**: Models wind advection and dispersion of falling foliage during drop via 2D Gaussian convolution:
   $$W_{\text{dispersed}}(x,y) = \iint W_{\text{direct}}(x', y') \cdot \frac{1}{2\pi \sigma^2} \exp\left( -\frac{(x-x')^2 + (y-y')^2}{2\sigma^2} \right) dx' dy'$$
   The dispersed load matrix is re-scaled to guarantee exact mass conservation ($\sum W_{\text{dispersed}} = \sum W_{\text{direct}}$) and clamped strictly to the forest footprint boundary.

##### Discrete Bounding Box Voxel/Vent Discretization
Continuous 2D spatial bulk density grids $\rho(x,y)$ are discretized into $N_{\text{bins}}$ discrete SURF classes. Neighboring cells within each grid row sharing identical SURF classes are automatically merged into single wide FDS `&VENT` rectangles, reducing total namelist entries in `.fds` files by up to 90% and accelerating CFD initialization.

##### Ground Fuel Spatial Raster Exports
When ground litter layers are generated (using Uniform, Model 1, or Model 2), TLS_to_FDS automatically exports 2D spatial raster grids, matrices, and visual heatmaps to the destination output folder for GIS analysis, numerical post-processing, and inspection:
- **`litter_bulk_density.tif`**: Standard GeoTIFF Raster Grid of 2D ground litter bulk density ($\text{kg/m}^3$). Features georeferenced spatial dimensions and native drag-and-drop compatibility with QGIS, ArcGIS, GDAL, and rasterio.
- **`litter_fuel_load.tif`**: Standard GeoTIFF Raster Grid of 2D surface fuel load ($W = \rho_{\text{litter}} \cdot h_{\text{litter}}$, $\text{kg/m}^2$).
- **`litter_bulk_density.png`**: High-resolution 2D visual heatmap preview displaying spatial axes in meters, colormap in $\text{kg/m}^3$, statistical metrics box (mean, min, max, std), and tree stem overlay coordinates (in Model 1).
- **`litter_fuel_load.png`**: High-resolution 2D visual heatmap preview displaying surface fuel load in $\text{kg/m}^2$.
- **`litter_bulk_density.csv`**: Plain-text CSV matrix of bulk density values ($\text{kg/m}^3$) for custom numerical scripting.
- **`litter_fuel_load.csv`**: Plain-text CSV matrix of surface fuel load values ($\text{kg/m}^2$) for custom numerical scripting.


---

## 4. Fire and Wind Settings

The **Fire and Wind Settings** module parameterizes atmospheric inflow dynamics, boundary layer velocity profiles, burner ignition geometry, and Lagrangian ember lofting kinetics.

---

### 4.1 Wind Field & Atmospheric Forcing

#### Physical & Numerical Basis
Wind forcing drives convective heat transfer ahead of the fire front, tilts flame structures, and accelerates rate of spread (RoS). In TLS_to_FDS, atmospheric wind is initialized at computational domain boundaries using open mesh inflow/outflow conditions (`&VENT MB='XMIN' /`, `&VENT MB='YMIN' /`, etc.) paired with logarithmic boundary layer velocity profiles.

To prevent numerical shocks and ensure realistic fire-atmosphere coupling:
- **Wind Development Time ($t_{\text{dev}}$)**: Fire simulations require a wind stabilization period prior to burner ignition. During $t_{\text{dev}}$, the CFD solver computes wind flow through the vegetative canopy obstacles, establishing logarithmic boundary layer turbulence and wake eddies across the domain before ignition begins.

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **Wind Development Time** | `spin_wind_dev` | `25.0 s` | Pre-ignition stabilization period ($t_{\text{dev}}$). Allows atmospheric boundary layer wind profiles to stabilize and traverse the domain before fire ignition commences. *(Ref: Simó-Martí et al., 2026)*. |
| **Wind Direction** | `spin_wind_dir` | `270º` | Meteorological wind origin direction: 0º (North), 90º (East), 180º (South), 270º (West, flowing East). Controls inflow/outflow mesh vent assignment. |
| **Wind Speed** | `spin_wind_speed` | `3.0 m/s` | Reference wind speed ($U_{\text{ref}}$) applied at the top of the atmospheric boundary layer or reference anemometer height. |

---

### 4.2 Atmospheric Boundary Layer Physics

#### Monin-Obukhov Similarity Theory Formulation
The atmospheric boundary layer (ABL) velocity profile $u(z)$ above the ground and through the canopy drag layer is parameterized via Monin-Obukhov Similarity Theory (MOST):
$$u(z) = \frac{u_*}{\kappa} \left[ \ln\left( \frac{z + z_0}{z_0} \right) - \psi_m\left( \frac{z}{L} \right) \right]$$
where $u_*$ is friction velocity, $\kappa = 0.41$ is the von Kármán constant, $z_0$ is aerodynamic roughness length, $L$ is the Obukhov length, and $\psi_m$ is the universal stability correction function.

In neutral atmospheric conditions ($|L| \to \infty$ or $L = -500\text{ m}$), thermal stability effects vanish ($\psi_m = 0$), reducing the formulation to the classic logarithmic law of the wall:
$$u(z) = \frac{u_*}{\kappa} \ln\left( \frac{z + z_0}{z_0} \right)$$
This ensures that wind speed drops smoothly to zero at the surface roughness height ($z_0$), preventing numerical pressure shocks at domain boundaries and establishing realistic vertical wind shear before ignition starts.

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **Obukhov Length ($L$)** | `spin_obukhov` | `-500.0 m` | Characterizes lower atmospheric thermal stability. $L < 0$ denotes unstable convective conditions (strong thermal updrafts); $L > 0$ denotes stable conditions; $-500\text{ m}$ or $\infty$ represents neutral stratification. *(Ref: Monin & Obukhov, 1954; FDS User Guide)*. |
| **Aerodynamic Roughness ($z_0$)** | `spin_z0` | `0.5 m` | Ground roughness length defining the height where logarithmic wind speed drops to zero. Standard Davenport-Wieringa terrain values: `0.03 m` (open grass), `0.25 m` (scattered trees), `0.5 m` (forest stands), `1.0 m` (closed forests). *(Ref: Wieringa, 1992)*. |

---

### 4.3 Ignition Boundary Setup

#### Thermal Pyrolysis Initiation & Supported Ignition Geometries
Ignition is simulated using artificial surface burner vents (`&VENT SURF_ID='IGN FIRE'`) located on the ground (`Z = 0`). The burner emits a specified Heat Release Rate Per Unit Area ($\text{HRRPUA}$, $\text{kW/m}^2$) for a finite duration ($t_{\text{ign}}$), radiating sufficient thermal energy to heat nearby vegetative voxels past their pyrolytic degradation threshold ($\approx 300^\circ\text{C}$).

TLS_to_FDS automatically calculates burner coordinates based on the unpadded forest bounding box footprint, supporting 8 standard ignition patterns:

- **Full-Width Line / Edge Fires**:
  - `Line: South Edge (y_min)`: Full-width ignition strip along the southern domain boundary ($Y_{\text{min}}$).
  - `Line: North Edge (y_max)`: Full-width ignition strip along the northern domain boundary ($Y_{\text{max}}$).
  - `Line: West Edge (x_min)`: Full-width ignition strip along the western domain boundary ($X_{\text{min}}$).
  - `Line: East Edge (x_max)`: Full-width ignition strip along the eastern domain boundary ($X_{\text{max}}$).
- **Corner Point Fires**:
  - `Point: South-West Corner`: Concentrated burner at $(X_{\text{min}}, Y_{\text{min}})$. Simulates simultaneous head-fire and flank-fire development under oblique wind angles.
  - `Point: South-East Corner`: Concentrated burner at $(X_{\text{max}}, Y_{\text{min}})$.
  - `Point: North-West Corner`: Concentrated burner at $(X_{\text{min}}, Y_{\text{max}})$.
  - `Point: North-East Corner`: Concentrated burner at $(X_{\text{max}}, Y_{\text{max}})$.

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **HRRPUA** | `spin_hrrpua` | `2500.0 kW/m²` | Heat Release Rate Per Unit Area for the ignition burner. Provides thermal energy required to initiate fuel pyrolysis. *(Ref: Babrauskas, 1984; Mell et al., 2007)*. |
| **Ignition Duration** | `spin_ign_duration` | `10.0 s` | Time duration the artificial ignition line remains active before shutting off. |
| **Ignition Vent Width** | `spin_vent_width` | `1.0 m` | Physical width of the ignition vent strip along the domain boundary. |
| **Ignition Pattern** | `combo_ign_pattern` | `Line: South Edge (y_min)` | Geometric footprint of ignition: 4 edge line fires or 4 corner point burners. Automatically snaps to vegetation outer bounds at $Z = 0$. |

---

### 4.4 Ember Transport and Firebrand Physics

#### Lagrangian Particle Tracking & Material Density Overrides
Spotting caused by lofted firebrands is a primary driver of rapid wildfire propagation and crown fire acceleration. When enabled, TLS_to_FDS activates FDS Lagrangian particle tracking (`EMBER_PARTICLE = .TRUE.`):

1. **Char & Ash Density Transitions**: Thermal degradation of vegetative fuel elements  produces char and ash residue. TLS_to_FDS automatically applies empirical material density overrides:
   $$\rho_{\text{char}} = 125.0\text{ kg/m}^3 \quad \text{and} \quad \rho_{\text{ash}} = 5.0\text{ kg/m}^3$$
   as established in empirical tree burning experiments *(Mell et al., 2026)*.
2. **Ember Lofting Thresholds**: As vegetation burns and mass is lost, particles meeting the **Ember Density Threshold** ($\rho_{\text{ember}} \le 62.5\text{ kg/m}^3$) are converted into discrete particles. If localized convective plume updrafts exceed the **Ember Velocity Threshold** ($W_{\text{updraft}} \ge W_{\text{threshold}}$), the firebrands break away and are advected downwind by the turbulent flow field.

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **Enable Ember Transport** | `check_track_embers` | `False` | Toggles Lagrangian firebrand particle generation. When active, TLS_to_FDS automatically applies empirical char density ($\rho_{\text{char}} = 180\text{ kg/m}^3$) and ash density ($\rho_{\text{ash}} = 50\text{ kg/m}^3$) material overrides. *(Ref: Mell et al., 2026)*. |
| **Ember Density Threshold** | `spin_ember_density` | `62.5 kg/m³` | Density threshold at which decaying vegetative particles convert into loftable char firebrands. |
| **Ember Velocity Threshold** | `spin_ember_velocity` | `0.0 m/s` | Critical localized updraft wind velocity required for aerodynamic lifting and firebrand breakaway into the plume flow. *(Ref: Manzello et al., 2008)*. |

---

## 5. Spatial Settings

The **Spatial Settings** module handles computational domain geometry, outer buffer padding, boundary snapping, coarse sky mesh generation, and parallel multi-core grid partitioning.

---

### 5.1 Domain Padding and Canopy Enclosure

#### Vertically Nested Multi-Grid Domain & Boundary Reflection Prevention
To prevent artificial CFD boundary constriction and numerical reflection:
1. **Lateral Padding ($X, Y$)**: Lateral domain extensions ensure inflow wind profiles stabilize before striking fuel obstacles and outflow plumes exit without artificial pressure feedback.
2. **Top Sky Mesh ($Z$)**: Plume rise above dense canopies requires vertical clearance. TLS_to_FDS enforces the rule $Z_{\text{max}} \ge 5 \times H_{\text{canopy}}$. To optimize cell counts, a **Vertically Nested Multi-Grid Domain** structure is used: a fine base mesh encloses the vegetation canopy ($\Delta x = \Delta y = \Delta z$), while a coarser sky mesh (e.g., $2\times$ or $3\times$ base cell size) covers the upper atmosphere.

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **X Domain Padding** | `spin_pad_x` | `10.0 m` | Lateral domain extension along the X axis. |
| **Y Domain Padding** | `spin_pad_y` | `10.0 m` | Inflow and outflow domain extension along the Y axis. |
| **Z Sky Padding** | `spin_pad_z` | `20.0 m` | Vertical height of coarse sky mesh placed above the forest canopy. Enforces $Z_{\text{max}} \ge 5 \times H_{\text{canopy}}$ to prevent top boundary flow constriction. *(Ref: McGrattan et al., 2013)*. |
| **Sky Mesh Multiplier** | `combo_sky_mult` | `2x` | Grid coarsening factor for upper sky mesh (e.g. $2\times \Delta x$). |
| **Domain Geometry Wizard** | `btn_domain_wizard` | *N/A* | Interactive tool that calculates optimal padding and multi-mesh grid dimensions based on target cell counts. |

---

### 5.2 Parallel Multi-Mesh MPI Subdivisions

#### High-Performance MPI Domain Decomposition
FDS uses Message Passing Interface (MPI) for domain decomposition, assigning individual 3D mesh blocks to separate CPU cores. TLS_to_FDS partitions the base domain along the X and Y axes into $\text{MPI}_X \times \text{MPI}_Y$ uniform sub-meshes, ensuring mesh boundaries align seamlessly with integer cell counts and coarse sky mesh boundaries.

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **MPI X Subdivisions** | `spin_mpi_x` | `2` | Number of mesh domain partitions along the X axis (`MPI_X`). |
| **MPI Y Subdivisions** | `spin_mpi_y` | `3` | Number of mesh domain partitions along the Y axis (`MPI_Y`). |

*Total Computational Meshes* = $(\text{MPI}_X \times \text{MPI}_Y) + 1_{\text{sky}}$ (e.g. $2 \times 3 = 6$ base meshes + 1 sky mesh = 7 parallel MPI processes).

---

## 6. Output Settings

The **Output Settings** module controls total simulation duration, diagnostic slice planes, boundary heat release rate maps, rate of spread trackers, and simulation restart checkpoints.

---

### 6.1 Simulation Timing and Volumetric Outputs

#### Simulation Duration & Diagnostic File Exports
Located within the **Output Settings** tab in the GUI, users configure total run duration alongside 2D/3D diagnostic output controls:

- **Surface Heat Release Rate (`&BNDF HRRPUA`)**: Generates 2D maps of ground surface heat release rate to track fire front progress, flame residence time, and fireline intensity.
- **Volumetric HRR (`&SLCF HRRPUV`)**: Slices 3D heat release rate per unit volume ($\text{kW/m}^3$) to visualize flame geometry, tilt angle, and flame height.
- **Gas Temperature & Velocity Slices (`&SLCF`)**: Slices gas temperature ($^\circ\text{C}$) and velocity vectors ($u, v, w$) to analyze plume buoyancy, crown scorch risk, and wind-fire coupling.

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **Total Simulation Time** | `spin_sim_time` | `240.0 s` | Total duration of the fire simulation in seconds (located in the Output Settings tab). |
| **HRRPUA (Boundary File)** | `check_out_hrrpua` | `True` | Exports 2D ground surface heat release rate maps (`&BNDF`). Essential for calculating Rate of Spread (RoS) and fireline intensity. |
| **Volumetric HRR (Slice)** | `check_out_flame` | `True` | Exports mid-plane 2D slices of volumetric heat release rate (`&SLCF` HRRPUV) to visualize 3D flame structure and flame height. |
| **Gas Temperature (Slice)** | `check_out_temp` | `True` | Exports mid-plane 2D gas temperature slices (`&SLCF`). Used for convective plume analysis and crown scorch modeling. |
| **Wind Velocity (Slice)** | `check_out_wind` | `True` | Exports 2D velocity vector slices (`&SLCF` U, W velocity) to analyze wind-fire coupling and fire-induced indrafts. |
| **Dry Biomass Tracking** | `check_out_biomass` | `False` | Tracks total dry fuel mass (kg) remaining in each vegetation stratum over time to determine percentage fuel consumption. |

---

### 6.2 Rate of Spread (RoS) Tracking

#### Transverse Temperature Front Arrival Trackers
To record exact fire front arrival times across the plot without manual post-processing, TLS_to_FDS can automatically insert 4 transverse device transect lines (`&DEVC`):
- Devices measure `MAXLOC X` or `MAXLOC Y` temperature statistics at 20%, 40%, 60%, and 80% span across the domain.
- Computes plot-scale Rate of Spread ($\text{m/s}$ or $\text{m/min}$) directly from device output time series.

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **Enable RoS Trackers** | `check_ros_tracking` | `False` | Generates 4 transverse device lines (`&DEVC`) measuring `MAXLOC X` or `MAXLOC Y` temperature statistics across domain span transects (at 20%, 40%, 60%, and 80% span). Automatically logs fire front arrival times across the plot. |

---

### 6.3 Multi-Height Slice Planes

#### Vertical Profiling Through Canopy Strata
Horizontal slice planes (`&SLCF`) can be requested at multiple vertical elevations $Z$:

| GUI Parameter | UI Widget | Default Value | Description, Logic & Scientific Basis |
| :--- | :--- | :--- | :--- |
| **Slice Heights (m)** | `line_slice_heights` | `"1.0"` | Comma-separated list of horizontal elevation planes (e.g. `0.5, 1.5, 2.5`) for multi-level `&SLCF` slice outputs. Enables vertical profiling of plume temperatures and horizontal wind speeds through understory and overstory canopy layers. |

---

### 6.5 Interactive 3D Pre-Simulation Scene Visualization

#### Pre-Flight Simulation Domain Inspection
Prior to executing computationally intensive CFD runs, TLS_to_FDS automatically generates an interactive 3D HTML visualization (`fds_scene_preview.html`) in the output destination folder. Built with Plotly 3D graphics, this lightweight, stand-alone file can be opened directly in any modern web browser without third-party plugins.

#### Key Visual Components & Physics Features
1. **Volumetric Voxel Cubes (`go.Mesh3d`)**:
   - Rather than simple point clouds or transparent overlapping blocks, voxels are rendered as true 3D solid cubic meshes.
   - Voxel faces are color-mapped using the continuous `YlOrRd` (Yellow-Orange-Red) thermal intensity colormap based on per-voxel bulk density ($\text{kg/m}^3$).
   - Direct face-level hover tooltips display exact $(X, Y, Z)$ centroid coordinates, cell dimensions, and bulk density.

2. **1D BFM Ground Litter Surface Layer**:
   - The 2D surface litter bed is rendered at $Z = 0$ strictly cropped to the unpadded forest footprint, ensuring outer computational padding remains clean and transparent.
   - Interactive hover tooltips provide position $(X, Y)$, bulk density ($\text{kg/m}^3$), fuel load ($\text{kg/m}^2$), and physical layer depth ($\text{cm}$).

3. **Tree Stems & Ignition Footprints**:
   - In Model 1, tree stem coordinates are projected onto the ground plane as distinct 3D markers and coordinate pins.
   - The selected ignition boundary pattern (South/North/East/West edges, SW/SE/NW/NE corners, or custom spot fire) is rendered as a bright red burner vent polygon at $Z = 0$.

4. **3D Inflow Wind Vector Arrows**:
   - Directional 3D wind velocity vector arrows (`go.Scatter3d`) are placed along the active domain boundary inflow face, visually confirming wind direction (degrees) and velocity magnitude ($U_{\text{ref}}$).

5. **Computational Domain & Coarse Sky Mesh Wireframes**:
   - Outer bounding boxes display the fine base domain and coarse sky mesh boundaries, allowing immediate visual verification of lateral domain padding and top sky clearance ($Z_{\text{max}} \ge 5 \times H_{\text{canopy}}$).

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
* **Simó-Martí, D., Laíño, D., et al. (2026)**. Integrating TLS-derived forest scenarios in FDS and sensitivity analysis of wind and fuel moisture on fire behavior. *Ecological Informatics* (under review).
* **Van Wagner, C.E. (1977)**. Conditions for start and spread of crown fire. *Canadian Journal of Forest Research*, 7(1), 23–34.
* **Wieringa, J. (1992)**. Updating the Davenport roughness classification for landscape terrain. *Journal of Wind Engineering and Industrial Aerodynamics*, 41(1-3), 357–368.
* **Wu, X., et al. (2023)**. Point Transformer V3: Simpler, Faster, Stronger. *arXiv preprint arXiv:2312.10035*.

---

## 8. Appendix A: Forest Biome Presets Reference

TLS_to_FDS includes pre-configured, literature-derived combustion property presets for common forest biomes:

### Preset Overview & Fuel Layer Matrix

| Biome Preset | Semantic Layer | Bulk Density ($\text{kg/m}^3$) | Moisture ($M_f$) | $S/V$ ($\text{m}^{-1}$) | Length $L$ ($\text{m}$) | Drag ($C_d$) | Embers |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Ponderosa Pine (Summer)** | Ladder Fuel | 0.40 | 1.00 (100%) | 3588 | 0.10 | 2.8 | Yes |
| | Surface Fuel | 0.80 | 0.15 (15%) | 8000 | 0.10 | 2.8 | Yes |
| | Ground Fuel | 1.20 | 0.15 (15%) | 9770 | 0.10 | 2.8 | Yes |
| | Trunks | 10.00 | 1.00 (100%) | 13 | 0.10 | 2.8 | Yes |
| | Litter | 15.00 | 0.05 (5%) | 6000 | 0.10 | 2.8 | Yes |
| **Ponderosa Pine (Winter)** | Ladder Fuel | 0.40 | 1.20 (120%) | 3588 | 0.10 | 2.8 | Yes |
| | Surface Fuel | 0.80 | 0.35 (35%) | 8000 | 0.10 | 2.8 | Yes |
| | Ground Fuel | 1.20 | 0.35 (35%) | 9770 | 0.10 | 2.8 | Yes |
| | Trunks | 10.00 | 1.10 (110%) | 13 | 0.10 | 2.8 | Yes |
| | Litter | 15.00 | 0.20 (20%) | 6000 | 0.10 | 2.8 | Yes |
| **European Mixed Forest (Summer)** | Ladder Fuel | 0.50 | 1.10 (110%) | 4500 | 0.10 | 2.8 | Yes |
| | Surface Fuel | 0.70 | 0.20 (20%) | 7500 | 0.10 | 2.8 | Yes |
| | Ground Fuel | 1.00 | 0.20 (20%) | 9000 | 0.10 | 2.8 | Yes |
| | Trunks | 12.00 | 1.00 (100%) | 13 | 0.10 | 2.8 | Yes |
| | Litter | 20.00 | 0.12 (12%) | 5500 | 0.10 | 2.8 | Yes |
| **European Mixed Forest (Winter)** | Ladder Fuel | 0.30 | 0.90 (90%) | 3000 | 0.10 | 2.8 | Yes |
| | Surface Fuel | 0.70 | 0.40 (40%) | 7500 | 0.10 | 2.8 | Yes |
| | Ground Fuel | 1.00 | 0.40 (40%) | 9000 | 0.10 | 2.8 | Yes |
| | Trunks | 12.00 | 1.10 (110%) | 13 | 0.10 | 2.8 | Yes |
| | Litter | 20.00 | 0.30 (30%) | 5500 | 0.10 | 2.8 | Yes |
| **Boreal Forest** | Ladder Fuel | 0.40 | 0.80 (80%) | 3588 | 0.10 | 2.8 | Yes |
| | Surface Fuel | 0.80 | 0.10 (10%) | 8000 | 0.10 | 2.8 | Yes |
| | Ground Fuel | 1.20 | 0.10 (10%) | 9770 | 0.10 | 2.8 | Yes |
| | Trunks | 10.00 | 0.90 (90%) | 13 | 0.10 | 2.8 | Yes |
| | Litter | 15.00 | 0.05 (5%) | 6000 | 0.10 | 2.8 | Yes |
| **Blank / Custom** | All Layers | *User-Defined* | *User-Defined* | *User-Defined* | 0.10 | 2.8 | *Configurable* |

---

## 9. Appendix B: Generated Output Files Summary

Upon clicking **Generate FDS Files**, TLS_to_FDS populates the selected output directory with simulation input scripts, binary matrices, rasters, and visual diagnostic tools:

| Output File Name | File Format | Purpose & Compatible Software |
| :--- | :--- | :--- |
| `<sim_name>.fds` | FDS Input Script (`.fds`) | Master simulation file containing complete mesh, atmospheric boundary, burner, and diagnostic output namelists. Run directly via `fds <sim_name>.fds`. |
| `<layer_name>.bdf` | Fortran Binary Data (`.bdf`) | C-vectorized unformatted Fortran sequential binary voxel arrays containing $(X, Y, Z)$ centroid coordinates and per-voxel bulk density ($\text{kg/m}^3$). Read automatically by FDS. |
| `fds_scene_preview.html` | Interactive 3D HTML Preview | Stand-alone 3D Plotly pre-simulation domain visualizer with cubic voxel meshes bulk-density-based colormaps, 3D wind vector arrows, tree stems, and burner footprints. Openable in any web browser. |
| `litter_bulk_density.tif` | GeoTIFF Raster (`.tif`) | Georeferenced 2D spatial raster grid of ground litter bulk density ($\text{kg/m}^3$). Native drag-and-drop support in QGIS, ArcGIS, GDAL, and Python rasterio. |
| `litter_fuel_load.tif` | GeoTIFF Raster (`.tif`) | Georeferenced 2D spatial raster grid of surface fuel load ($W = \rho_{\text{litter}} \cdot h$, $\text{kg/m}^2$). |
| `litter_bulk_density.png` | Publication PNG Heatmap | High-resolution 2D visual heatmap showing spatial axes in meters, colormap in $\text{kg/m}^3$, statistical metrics box (mean, min, max, std), and tree stem coordinates (in Model 1). |
| `litter_fuel_load.png` | Publication PNG Heatmap | High-resolution 2D visual heatmap showing surface fuel load in $\text{kg/m}^2$. |
| `litter_bulk_density.csv` | Numerical CSV Matrix | Plain-text numerical matrix of 2D bulk density values ($\text{kg/m}^3$) for custom mathematical scripting and spreadsheet analysis. |
| `litter_fuel_load.csv` | Numerical CSV Matrix | Plain-text numerical matrix of 2D surface fuel load values ($\text{kg/m}^2$). |
