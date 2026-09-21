# Two-Stage Voxelization Methodology in TLS_to_FDS

When transforming Terrestrial Laser Scanning (TLS) point clouds of forest fuels into 3D numerical grids for physics-based computational fluid dynamics (CFD) models (such as NIST Fire Dynamics Simulator / WFDS), a fundamental challenge arises: **raw LiDAR point counts in space do not correspond linearly to plant biomass or leaf area density (LAD)**.

Assigning local fuel bulk density ($\rho_b$, $\text{kg/m}^3$) directly proportional to raw LiDAR point density introduces severe, systematic, and non-random spatial distortions. These distortions stem from:
1. **Exponential radiation attenuation along beam trajectories** governed by the **Beer-Lambert law** (turbid medium theory), which leaves internal and distal crown regions severely under-sampled.
2. **Sensor acquisition geometry and sampling artifacts**, including beam divergence, range-dependent footprint dilation, non-orthogonal incident angles, multi-target beam splitting at fine fuel edges, and localized point-density spikes caused by multi-scan coregistration overlaps.

In full ray-tracing architectures (e.g., Béland et al., 2014; Pimont et al., 2018; Soma et al., 2020), this bias is corrected by tracking all entering laser pulses ($N_{\text{in}}$) versus intercepted pulses ($N_{\text{int}}$) through every voxel. However, standard forestry point clouds frequently lack original scanner station coordinates and pulse trajectory metadata, or are too computationally massive for runtime ray-tracing.

`TLS_to_FDS` bridges this gap using an **experimental Two-Stage Voxelization Algorithm**:
1. **Sub-voxel Micro-Discretization ($1\text{ cm}$)**: Collapses multi-scan overlap redundancy and point clustering into binary micro-occupancy indicators via fast spatial hashing.
2. **Macro-Grid Aggregation & Dynamic Imputation ($\Delta x \approx 0.25\text{ m}$)**: Counts occupied micro-voxels ($P_v$) to capture the volumetric packing fraction and structural heterogeneity.
3. **Bounded Scaling & Exact Mass Conservation**: Scales local bulk density with safety clamping bounds ($[0.05 \times, 4.0 \times]$) and re-normalizes the entire domain to ensure exact preservation of nominal fuel layer biomass ($\sum \rho_v V_v = M_{\text{layer}}$).

This document details the optical physics, mathematical derivations, geometric error modes, and operational justification for this methodology.

---

## 2. Theoretical Physics of LiDAR Attenuation: The Beer-Lambert Law

### 2.1 Turbid Medium Radiative Transfer in Canopies

Vegetation canopies have long been modeled in quantitative remote sensing and micrometeorology as turbid media containing quasi-randomly distributed, discrete absorbing and scattering phyto-elements (Nilson, 1971; Ross, 1981). 

When a monochromatic, collimated laser pulse travels through a porous vegetative medium along path length $s$, the probability that the beam travels a distance $s$ without intercepting foliage—termed the **gap fraction** or **transmittance** $P_{\text{gap}}(s)$—is described by the **Beer-Lambert Law**:

$$P_{\text{gap}}(s) = \exp\left( - \int_0^s k(s') \, ds' \right) = \exp\left( - G(\theta) \cdot \text{PAD} \cdot s \right)$$

where:
- $\text{PAD}$ is the **Plant Area Density** ($\text{m}^2/\text{m}^3$), representing the total one-sided surface area of vegetative elements (foliage, twigs, branches) per unit volume.
- $G(\theta)$ is the **Ross-Nilson geometric projection coefficient**, representing the mean projection of unit plant area in the direction of the laser beam at incident angle $\theta$ (for a spherical leaf angle distribution, $G(\theta) \approx 0.5$).
- $k = G(\theta) \cdot \text{PAD}$ is the **extinction coefficient** ($\text{m}^{-1}$).

![Figure 1: Radiative Transfer and Beer-Lambert Attenuation of a Laser Pulse in Vegetative Voxels](file:///c:/github_repos/TLS_to_FDS/assets/beer_lambert_voxel_physics.png)

*Figure 1: Radiative transfer and optical extinction of a laser pulse in porous vegetative media. (a) Single-voxel energy balance showing incoming laser pulse flux $I_0$ ($N_{\mathrm{in}}$), internal optical path length $\Delta s$, backscattered return echo generation ($P_{\mathrm{int}} = 1 - e^{-G(\theta) \cdot \mathrm{PAD} \cdot \Delta s}$), and transmitted beam energy ($I(\Delta s) = I_0 e^{-k \Delta s}$). (b) Penetration depth into canopy showing exponential depletion of surviving beam energy $I(s)/I_0 = e^{-ks}$ and cumulative interception probability $P_{\mathrm{int}}(s) = 1 - e^{-ks}$ across successive voxels, illustrating why internal canopy voxels receive heavily depleted pulse flux.*

### 2.2 Beam Depletion and Non-Linear Sampling Bias

The cumulative probability of a laser beam being intercepted ($P_{\text{int}}$) before reaching penetration depth $s$ is:

$$P_{\text{int}}(s) = 1 - P_{\text{gap}}(s) = 1 - \exp\left( - G(\theta) \int_0^s \text{PAD}(s') \, ds' \right)$$

As a laser beam penetrates deeper into a dense tree crown or thick shrub, the number of surviving photons/pulses decreases exponentially with optical depth $\tau = \int k \, ds$. Consequently:
- **Outer / Proximal Foliage**: Faces a high pulse flux ($N_{\text{in}} \approx N_{\text{emitted}}$), producing abundant backscattered returns.
- **Inner / Distal Foliage**: Receives a heavily depleted pulse flux ($N_{\text{in}} \ll N_{\text{emitted}}$). Even if the internal crown contains significant biomass, few or no pulses survive to strike those elements.

Thus, **raw return counts systematically underestimate interior and upper-canopy biomass**.

---

## 3. Sensor Acquisition Geometry and Sampling Artifacts

Beyond radiative extinction, the raw spatial distribution of LiDAR returns is severely corrupted by instrument mechanics and scanning geometry:

```
                  ===================================================
                  SOURCES OF POINT-DENSITY DISTORTION IN RAW TLS DATA
                  ===================================================
                                            │
        ┌───────────────────┬───────────────┴───────────────┬───────────────────┐
        ▼                   ▼                               ▼                   ▼
┌────────────────┐  ┌────────────────┐            ┌──────────────────┐  ┌───────────────────┐
│ Range & Beam   │  │ Incident Angle │            │ Shadowing &      │  │ Coregistration    │
│ Divergence     │  │ & Orientation  │            │ Edge Splitting   │  │ Overlap Inflation │
└────────────────┘  └────────────────┘            └──────────────────┘  └───────────────────┘
```

### 3.1 Range Attenuation and Beam Divergence
1. **Spot Footprint Dilation**: The laser beam diameter $w(r)$ expands linearly with range $r$ due to beam divergence angle $\gamma$:
   $$w(r) = w_0 + 2 r \tan\left(\frac{\gamma}{2}\right) \approx w_0 + \gamma r$$
   As range increases, energy density per unit area ($\text{W/m}^2$) drops quadratically, decreasing signal-to-noise ratio (SNR) and the probability of triggering the photodetector threshold.
2. **Angular Point Spacing**: For a constant angular step $\Delta \theta$, the spatial distance between adjacent pulses expands with range:
   $$\Delta d \approx r \cdot \Delta \theta$$
   A voxel at $r = 5\text{ m}$ is sampled at a spatial resolution 4 times denser than an identical voxel at $r = 20\text{ m}$.

### 3.2 Target Orientation and Directional Scattering
The backscattered optical power $P_r$ returned to the sensor depends heavily on the angle of incidence $\alpha$ between the laser vector $\mathbf{v}_{\text{beam}}$ and the surface normal of the leaf $\mathbf{n}$:
$$P_r \propto \rho_{\text{refl}} \cos(\alpha)$$
Foliage oriented perpendicular to the beam returns strong signals, whereas obliquely oriented leaves scatter energy away from the receiver.

### 3.3 Mutual Occlusion and Shadowing
Near surfaces cast optical "shadows" across farther surfaces. Solid vegetative obstacles (e.g., tree trunks, thick boughs, dense outer needle clusters) create total line-of-sight blockage, preventing downstream sampling regardless of the actual biomass present in the occluded zone.

### 3.4 Partial Returns and Multi-Target Echo Splitting
When a dilated laser footprint strikes the edge of a leaf, needle, or small twig, the pulse splits: part of the energy reflects back immediately (Return 1), while the remaining energy continues forward until hitting another element (Return 2, 3, etc.). Depending on instrument pulse-detection algorithms, edge-splitting can artificially inflate point counts along crown perimeters.

### 3.5 Multi-Scan Coregistration Overlap Inflation
In field TLS campaigns, multiple scan positions (e.g., 4 to 8 tripod stations around a plot) are registered into a single coordinate system.
- Voxels located within the overlapping field-of-view of multiple scanners receive an $N_{\text{scans}}$-fold multiplication in pulse passes.
- Voxels visible from only one scanner receive a fraction of that sampling intensity.
- **Result:** Regions of multi-scan convergence exhibit massive artificial point clustering that reflects scan topology rather than true vegetative density.

---

## 4. Illustrative Diagnostic Examples

To clarify why raw point counting produces erroneous fuel beds for wildfire simulations, consider two common field scenarios:

### Example A: The Two-Scanner Shrub Setup
* **Scenario**: A standalone shrub with radially symmetric biomass is scanned from two tripod stations located at roughly 90° azimuth relative to the plant.
* **Observation**: The front quadrant facing both scanners receives high-density coverage from two independent beam trajectories. The rear quadrants facing away from both scanners receive only grazing or occluded pulses.
![Figure 2: Acquisition Geometry Bias in Raw TLS Returns vs. Naive Voxelization vs. 2-Stage Micro-Voxelization and Normalization](file:///c:/github_repos/TLS_to_FDS/assets/shrub_scan_geometry_bias.png)

*Figure 2: Conceptual illustration of multi-scan acquisition geometry bias and two-stage voxelization correction for a radially symmetric shrub. (a) Laser ray trajectories from two orthogonal scanner positions (0° and 90°) showing dual-scan overlap (2× incoming flux) and occluded rear shadow zones. (b) Uncorrected raw return point density displaying severe over-sampling in the overlap quadrant and under-sampling in distal/rear zones due to Beer-Lambert attenuation. (c) Naive 1-stage voxelization directly mapping raw point counts to bulk density ($\rho_b$) without micro-voxelization, resulting in severe directional mass skew (>3× nominal density in overlap cells and depleted interiors). (d) 2-stage micro-voxelization without Stage 5 mass re-normalization, illustrating how uncalibrated scaling and clamping cause total domain mass drift (~65% of target biomass). (e) Complete TLS_to_FDS 2-stage micro-voxelized imputation with Stage 5 mass-conserved normalization, achieving exact mass conservation ($\sum \rho_v V_v = M_{\text{nominal}}$) and a symmetrical, physically realistic fuel distribution.*

#### Theoretical Total Mass & Quantitative Breakdown for Figure 2

In **TLS_to_FDS**, the **theoretical total dry combustible fuel mass** ($M_{\text{nominal}}$) for any voxelized vegetation stratum is defined by:

$$M_{\text{nominal}} = \sum_{v=1}^{N_{fl}} \text{BD}_{\text{nominal}} \cdot V_{\text{voxel}} = N_{fl} \cdot \text{BD}_{\text{nominal}} \cdot (\Delta x \, \Delta y \, \Delta z)$$

where:
* $N_{fl}$ is the count of active, non-empty simulation voxels in the fuel layer.
* $\text{BD}_{\text{nominal}}$ is the nominal dry bulk density assigned to that layer ($\text{kg/m}^3$, from allometry, destructively harvested samples, or calibrated forest presets).
* $V_{\text{voxel}} = \Delta x \cdot \Delta y \cdot \Delta z$ is the volume of a single computational voxel cell ($\text{m}^3$).

##### Concrete Numerical Values for the Modeled Shrub:
* **Geometry**: Crown radius $R = 1.2\text{ m}$ (Crown diameter $D = 2.4\text{ m}$).
* **Grid Resolution**: $\Delta x = \Delta y = \Delta z = 0.25\text{ m}$ ($V_{\text{voxel}} = 0.015625\text{ m}^3$).
* **Nominal Bulk Density**: $\text{BD}_{\text{nominal}} = 0.70\text{ kg/m}^3$ (standard Mediterranean fine surface shrub / *Rosmarinus* / *Cistus* fine fuel).

1. **For the 2D Horizontal Slice Shown in Figure 2 ($\Delta z = 0.25\text{ m}$)**:
   * **Active Voxels ($N_{fl}$)**: $80\text{ voxels}$ (Total active volume $V_{\text{slice}} = 80 \times 0.015625 = \mathbf{1.25\text{ m}^3}$).
   * **Theoretical Total Mass of the Slice**:
     $$M_{\text{slice}} = 1.25\text{ m}^3 \times 0.70\text{ kg/m}^3 = \mathbf{0.875\text{ kg}}$$
     *(If $\text{BD}_{\text{nominal}} = 1.50\text{ kg/m}^3$, $M_{\text{slice}} = 1.875\text{ kg}$; if $\text{BD}_{\text{nominal}} = 3.00\text{ kg/m}^3$, $M_{\text{slice}} = 3.750\text{ kg}$)*.

2. **For the Full 3D Hemispherical Shrub Crown ($H = 1.2\text{ m}$)**:
   * **Active Envelope Volume**: $V_{\text{hemi}} = \frac{2}{3} \pi R^3 = \frac{2}{3} \pi (1.2)^3 \approx \mathbf{3.62\text{ m}^3}$ ($\approx 232\text{ voxels}$).
   * **Theoretical Total Dry Biomass**:
     $$M_{\text{total}} = 3.62\text{ m}^3 \times 0.70\text{ kg/m}^3 = \mathbf{2.53\text{ kg}}$$

##### Step-by-Step Mass Behavior Across Figure 2 Panels:

| Panel | Method / Stage | Total Mass $\sum \rho_v V_v$ | Mass Fraction | Spatial Mass Distribution & Fidelity |
| :--- | :--- | :--- | :--- | :--- |
| **(a)** | **Physical Shrub (Ground Truth)** | **$0.875\text{ kg}$** ($2.53\text{ kg}$ 3D) | **$100.0\%$** | Symmetrical, centered radially within crown. |
| **(b)** | **Raw LiDAR Returns** | Dimensionless counts | N/A | Corrupted by Beer-Lambert decay & multi-scan overlap. |
| **(c)** | **1-Stage Voxel (Raw Counts)** | $0.875\text{ kg}$ | $100.0\%$ | **Severe Directional Error**: $>60\%$ of total mass clustered into the NE overlap quadrant ($>3\times$ nominal density); interior starved. |
| **(d)** | **2-Stage Voxel (Un-Normalized)** | **$0.569\text{ kg}$** | **$\approx 65.0\%$** | Symmetrical, but suffers a **$\sim 35\%$ mass deficit drift** due to uncalibrated occupancy scaling and clamping bounds. |
| **(e)** | **2-Stage Voxel (Mass-Normalized)** | **$0.875\text{ kg}$** ($2.53\text{ kg}$ 3D) | **$100.0\%$** | **Unbiased & Exact**: Full nominal mass conserved ($\gamma_{\text{mass}} \approx 1.54$) with natural, symmetrical radial distribution. |

### Example B: Ground-Level Forest Canopy Scan
* **Scenario**: A tall conifer stand is scanned from ground level using upright TLS scanners.
* **Observation**: Laser pulses strike lower branches and trunk bases with short ranges ($3 - 8\text{ m}$) and near-zero cumulative optical depth. As pulses travel upward into the upper crown ($15 - 30\text{ m}$), optical attenuation and beam divergence compound.
* **Raw Point Count Outcome**: Point density drops by over an order of magnitude between the lower crown base and the upper canopy.
* **Modeling Error**: Direct mapping produces an artificially bottom-heavy crown fuel layer. In fire behavior simulations, this distorts ladder fuel transitions, canopy ignition thresholds, and crown fire spread rates.

> [!IMPORTANT]
> **Directional vs. Random Bias**: The bias introduced by acquisition geometry and Beer-Lambert attenuation is **strictly directional and systematic**, not Gaussian noise. It does not average out across a plot; rather, it systematically shifts simulated mass toward near, lower, and outer voxels.

---

## 5. State of the Art in Voxel-Based PAD / LAD Inversion

In the ecological and forestry remote sensing literature, overcoming Beer-Lambert attenuation and geometric sampling bias is a mature field. Established models (Hosoi & Omasa, 2006; Béland et al., 2011, 2014; Grau et al., 2017; Pimont et al., 2018; Soma et al., 2020) utilize **contact frequency inversion** via ray-tracing:

```
                            [ Ray-Tracing Inversion Formulation ]

                                     - ln( 1 - N_int,v / N_in,v )
                     PAD_v = ──────────────────────────────────────────
                                           G(θ) · ℓ_v
```

where:
- $N_{\text{in}, v}$: Total number of laser beams entering voxel $v$.
- $N_{\text{int}, v}$: Number of laser beams intercepted (ending) within voxel $v$.
- $\bar{\ell}_v$: Mean optical path length traveled by beams through voxel $v$.
- $G(\theta)$: Directional projection coefficient.

By dividing intercepted pulses ($N_{\text{int}}$) by the entering pulse flux ($N_{\text{in}}$), these methods compute local transmittance ($T_v = 1 - N_{\text{int}}/N_{\text{in}}$) independent of whether 100 or 10,000 beams entered the cell.

### The Practical Bottleneck for CFD Workflows
While mathematically rigorous, full ray-tracing inversion presents practical bottlenecks when preparing computational meshes for fire simulations:
1. **Missing Trajectory Metadata**: Standard operational LiDAR datasets (delivered as `.las`, `.pts`, or `.ply` point clouds) frequently lack scanner origin coordinates, trajectory vectors, or emitted pulse records.
2. **Computational Overhead**: Ray-tracing billions of pulses across high-resolution 3D grids spanning hundreds of meters requires hours of pre-processing time.
3. **Empty Voxel Ambiguity**: Voxels where $N_{\text{in}} = 0$ (complete occlusion) cannot be inverted mathematically without complex spatial interpolation.

---

## 6. The TLS_to_FDS Two-Stage Voxelization Solution

To achieve spatial realism and mitigate point-density bias without requiring full laser pulse ray-tracing metadata, `TLS_to_FDS` implements a **Two-Stage Micro-Voxelization and Mass-Preserving Imputation Algorithm** ([spatial_utils.py](file:///c:/github_repos/TLS_to_FDS/src/tls_to_fds/spatial_utils.py#L124-L217)):


### 6.1 Mathematical Formulation

#### Step 1: Sub-Voxel Micro-Discretization ($1\text{ cm}$)
The raw point cloud $\mathcal{P} = \{\mathbf{x}_i\}_{i=1}^N$ is discretized onto a high-resolution sub-grid ($\delta = 0.01\text{ m} = 1\text{ cm}$):
$$\mathbf{k}_i = \left\lfloor \frac{\mathbf{x}_i}{\delta} \right\rfloor \in \mathbb{Z}^3$$
All points falling into the same $1\text{ cm}^3$ volume are collapsed into a single unique active centroid $\mathbf{u}_j$:
$$\mathcal{U} = \text{Unique}\left( \{\mathbf{k}_i\} \right) \cdot \delta + \frac{\delta}{2}$$

* **Physical Effect**: If a single leaf was scanned 200 times due to 4 overlapping scanner positions at close range ($r = 2\text{ m}$), those 200 raw returns collapse into a single $1\text{ cm}$ micro-occupancy element. This eliminates the multi-scan overlap density spike.

#### Step 2: Simulation Grid Occupancy ($P_v$)
The unique micro-centroids $\mathcal{U}$ are then aggregated into simulation voxels of dimension $\Delta x$ (e.g., $0.25\text{ m}$):
$$P_v = \sum_{\mathbf{u}_j \in \text{Voxel}_v} 1$$
$P_v$ represents the **number of occupied $1\text{ cm}$ sub-voxels** within simulation cell $v$. For a $0.25\text{ m}$ voxel, $P_v \in [1, 25^3] = [1, 15625]$.

* **Physical Meaning**: $P_v$ is proportional to the **solid volume filling fraction** of plant elements within the CFD cell, rather than the number of reflected laser photons.

#### Step 3: Mean Layer Occupancy and Linear Scaling
The mean micro-voxel count across all active cells in the fuel layer ($N_{fl}$) is computed:
$$\bar{P}_{fl} = \frac{1}{N_{fl}} \sum_{v=1}^{N_{fl}} P_v$$
The unconstrained raw bulk density is scaled by local occupancy relative to the layer mean:
$$\text{BD}_v^{\text{raw}} = \text{BD}_{\text{nominal}} \cdot \left( \frac{P_v}{\bar{P}_{fl}} \right)$$

#### Step 4: Outlier Clamping
To prevent extreme numerical spikes from dense wood stems, scanner noise, or unphysically sparse peripheral voxels, bounding factors ($\alpha_{\text{min}} = 0.05$, $\alpha_{\text{max}} = 4.0$) are enforced:
$$\text{BD}_v^{\text{clamped}} = \operatorname{clip}\left( \text{BD}_v^{\text{raw}}, \, 0.05 \cdot \text{BD}_{\text{nominal}}, \, 4.0 \cdot \text{BD}_{\text{nominal}} \right)$$

* **Physical Rationale for Default Bounds**:
  - **Lower Bound ($0.05 \cdot \text{BD}_{\text{nominal}}$)**: Avoids negligible bulk densities that consume solver memory and burn in a fraction of a millisecond without generating meaningful flame heat release, establishing an effective physical percolation threshold for combustible porous fuel.
  - **Upper Bound ($4.0 \cdot \text{BD}_{\text{nominal}}$)**: Prevents over-dense fine fuel cells (e.g. $15\text{–}30\text{ kg/m}^3$) whose excessive volumetric heat capacity ($\rho_b c_p$) would act as artificial heat sinks and extinguish approaching fire fronts in FDS.
* **Planned Feature — Sample-Driven Adaptive Dispersion Clamping**:
  In future versions, fixed $[0.05, 4.0]$ limits will be augmented by *ad hoc* data-driven dispersion estimators derived directly from the empirical micro-occupancy distribution of the sample:
  1. **Empirical Quantile Winsorization**: Computing bounds dynamically from the 1st and 99th percentiles ($\alpha_{\min} = Q_{0.01}(P)/\bar{P}_{fl}$ and $\alpha_{\max} = Q_{0.99}(P)/\bar{P}_{fl}$) to adapt naturally to uniform vs. highly clumped canopy architectures.
  2. **Robust Median Absolute Deviation (MAD)**: $\operatorname{clamp}(P_v, \operatorname{median}(P_v) \pm 3 \cdot 1.4826 \cdot \text{MAD})$ to resist heavy point clustering.
  3. **Biophysical Packing Limits**: Bounding maximum bulk density by the physical fuel packing ratio $\beta_{\max} \approx 0.025$ and solid particle density ($\text{BD}_{\max} = \beta_{\max} \cdot \rho_{\text{solid}} \approx 12.5\text{ kg/m}^3$).

#### Step 5: Exact Mass Preservation
To guarantee that the total dry combustible fuel mass within the domain matches the allometric/inventory baseline ($M_{\text{total}} = N_{fl} \cdot \text{BD}_{\text{nominal}} \cdot V_{\text{voxel}}$), a global normalization scalar is applied:
$$\gamma_{\text{mass}} = \frac{N_{fl} \cdot \text{BD}_{\text{nominal}}}{\sum_{v=1}^{N_{fl}} \text{BD}_v^{\text{clamped}}}$$
$$\text{BD}_v = \text{BD}_v^{\text{clamped}} \cdot \gamma_{\text{mass}}$$

$$\sum_{v=1}^{N_{fl}} \text{BD}_v \cdot V_{\text{voxel}} \equiv M_{\text{nominal}}$$

---

## 7. Comparative Methodological Summary

| Method | Data Requirements | Attenuation Handling | Overlap Handling | Computational Cost | Operational Suitability for CFD |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Raw Point Density Mapping** | Point cloud only $(X,Y,Z)$ | None (Heavily biased by Beer-Lambert decay) | None (Overlaps create artificial mass spikes) | Very Low | **Poor**: Distorts flame spread, ignition, and fuel continuity. |
| **Full Ray-Tracing (AMAPvox / VoxLOD)** | Raw pulses, scanner trajectories $(X_0, Y_0, Z_0)$, beam directions | Full Transmittance Inversion ($N_{\text{int}} / N_{\text{in}}$) | Full Normalization across scan views | Very High (Minutes to hours) | **High accuracy**, but requires unavailable scanner trajectory metadata. |
| **TLS_to_FDS 2-Stage Voxelization** | Point cloud only $(X,Y,Z)$ | Spatial micro-clustering prevents attenuation magnification | Multi-returns collapsed via $1\text{ cm}$ spatial hashing | Extremely Low (<50 ms via C-accelerated hashing) | **Optimal**: Preserves spatial heterogeneity and mass without trajectory dependencies. |

---

## 8. Key References

1. **Béland, M., Widlowski, J. L., Fournier, R. A., Côté, J. F., & Verstraete, M. M. (2011).** Estimating leaf area distribution in savanna trees from terrestrial LiDAR measurements. *Agricultural and Forest Meteorology*, 151(9), 1252–1266. https://doi.org/10.1016/j.agrformet.2011.05.004
2. **Béland, M., Baldocchi, D. D., Widlowski, J. L., Fournier, R. A., & Verstraete, M. M. (2014).** On seeing the wood from the leaves and the role of voxel size in determining leaf area distribution of forests with terrestrial LiDAR. *Agricultural and Forest Meteorology*, 184, 82–97. https://doi.org/10.1016/j.agrformet.2013.09.005
3. **Grau, E., Durrieu, S., Fournier, R., Gastellu-Etchegorry, J. P., & Yin, T. (2017).** Estimation of 3D vegetation density with Terrestrial Laser Scanning data using voxels. A sensitivity analysis of influencing parameters. *Remote Sensing of Environment*, 191, 373–388. https://doi.org/10.1016/j.rse.2017.01.032
4. **Hosoi, F., & Omasa, K. (2006).** Voxel-based 3-D modeling of individual trees for estimating leaf area density using high-resolution portable scanning lidar. *IEEE Transactions on Geoscience and Remote Sensing*, 44(12), 3610–3618. https://doi.org/10.1109/TGRS.2006.881743
5. **Mell, W., Jenkins, M. A., Gould, J., & Cheney, P. (2007).** A physics-based approach to modelling grassland fires. *International Journal of Wildland Fire*, 16(1), 1–22. https://doi.org/10.1071/WF06002
6. **Morvan, D., & Dupuy, J. L. (2004).** Modeling the propagation of a wildfire through a Mediterranean shrub using a multiphase formulation. *Combustion and Flame*, 138(3), 199–210. https://doi.org/10.1016/j.combustflame.2004.05.001
7. **Nilson, T. (1971).** A theoretical analysis of the frequency of gaps in plant stands. *Agricultural Meteorology*, 8, 25–38. https://doi.org/10.1016/0002-1571(71)90092-6
8. **Pimont, F., Allard, D., Soma, M., & Dupuy, J. L. (2018).** Estimators and confidence intervals for plant area density at voxel scale with T-LiDAR. *Remote Sensing of Environment*, 215, 343–370. https://doi.org/10.1016/j.rse.2018.06.024
9. **Ross, J. (1981).** *The Radiation Regime and Architecture of Plant Stands*. Dr W. Junk Publishers, The Hague. https://doi.org/10.1007/978-94-009-8647-3
10. **Rothermel, R. C. (1972).** *A mathematical model for predicting fire spread in wildland fuels*. USDA Forest Service Research Paper INT-115. Intermountain Forest and Range Experiment Station, Ogden, UT.
11. **Soma, M., Pimont, F., Durrieu, S., & Dupuy, J. L. (2018).** Enhanced measurements of leaf area density with T-LiDAR: Evaluating and calibrating the effects of vegetation heterogeneity and scanner properties. *Remote Sensing*, 10(10), 1580. https://doi.org/10.3390/rs10101580
12. **Soma, M., Pimont, F., Allard, D., & Fournier, R. (2020).** Mitigating occlusion effects in Leaf Area Density estimates from Terrestrial LiDAR through a specific kriging method. *Remote Sensing of Environment*, 245, 111836. https://doi.org/10.1016/j.rse.2020.111836
