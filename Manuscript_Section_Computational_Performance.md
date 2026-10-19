# Manuscript Subsection Draft: Computational Performance and Algorithmic Scalability

> **Target Publication**: *Computers and Electronics in Agriculture* (*COMPAG*, Elsevier)  
> **Section Title**: 3. Computational Performance, Algorithmic Scalability, and Memory Efficiency  
> **Manuscript Type**: Application Note / Original Research Article  
> **Accompanying Figure**: Figure 3 (`assets/fig_computational_benchmarks.pdf` / `assets/fig_computational_benchmarks.png`)  
> **Accompanying Tables**: Table 1, Table 2, Table 3 (`benchmark_results/`)

---

## 3. Computational Performance and Algorithmic Scalability

### 3.1 Empirical Benchmark Configuration and Plot Architecture

To rigorously evaluate the computational throughput, memory footprint, and scalability of the `TLS_to_FDS` conversion pipeline under operational forestry research conditions, empirical benchmarks were conducted using real Terrestrial Laser Scanning (TLS) point clouds rather than idealized synthetic geometric shapes. 

The evaluation dataset was collected from a $40 \times 40\text{ m}^2$ ($1600\text{ m}^2$) mature *Pinus ponderosa* forest stand in the **Sycan Marsh Preserve** (Klamath County, Oregon, USA; $42^\circ 48'\text{ N}, 120^\circ 56'\text{ W}$). The plot represents a complex multi-layered structure comprising:
1. An overstory canopy stratum (`test_ladder_fuels.laz`; 2,597,582 discrete returns) characterized by variable crown clumping, mature bole architectures, and discontinuous needle foliage.
2. A dense understory and surface fuel stratum (`test_surface_fuels.laz`; 2,354,064 discrete returns) comprising bitterbrush (*Purshia tridentata*), sagebrush (*Artemisia tridentata*), and mixed graminoids.

In total, **4,951,646 raw georeferenced TLS returns** were processed simultaneously using the literature-derived `ponderosa_pine_summer.json` biome preset. All benchmarks were executed on a workstation equipped with an Intel Core i9 processor (32 logical threads), 32 GB of RAM, and solid-state NVMe storage, running 64-bit Windows 11 and Python 3.13.5 with NumPy 2.5.0, SciPy 1.18.0, and `laspy` 2.7.0. Execution times were recorded using monotonic, high-resolution performance counters (`time.perf_counter()`) across $N = 3$ independent runs per condition to quantify measurement repeatability (mean $\pm$ standard deviation).

---

### 3.2 3D Voxel Resolution Scaling and Vectorized Fortran I/O Throughput

CFD wildfire simulations in FDS are highly sensitive to grid resolution, which dictates both flame front resolution and total cell count. We evaluated pipeline behavior across a fine-to-coarse grid resolution gradient:
$$\Delta x \in \{1.00, \, 0.50, \, 0.30, \, 0.25, \, 0.20, \, 0.15, \, 0.10\}\text{ m}$$

As presented in **Table 1** and illustrated in **Figure 3(a)**, the active porous voxel count ($N_v$) scales inversely with grid cell volume:
$$N_v \propto \Delta x^{-3}$$
ranging from 1,573 active cells at $\Delta x = 1.00\text{ m}$ to 303,365 active cells at $\Delta x = 0.10\text{ m}$.

Remarkably, despite a **192-fold increase** in the number of generated simulation voxels, the 3D dynamic micro-voxelization execution time remained essentially constant, fluctuating narrowly between $0.262 \pm 0.018\text{ s}$ and $0.294 \pm 0.021\text{ s}$. This stability demonstrates the architectural advantage of the **Two-Stage Voxelization Algorithm**:
* **Stage 1 (Sub-voxel Micro-Discretization)** operates directly on the 4.95 million raw returns using C-accelerated spatial micro-hashing at $\delta = 1\text{ cm}$. Because this step indexes points into integer grid hash bins in strict linear time ($\mathcal{O}(N_{\text{pts}})$), point-cloud decimation and multi-scan coregistration overlap collapsing are completely decoupled from the destination CFD grid cell size $\Delta x$.
* **Stage 2 (Macro-Grid Aggregation and Bounded Scaling)** aggregates only the unique micro-voxels into target cells $\Delta x$, performing vector arithmetic and mass normalization ($\sum \rho_v V_v = M_{\text{layer}}$) in negligible computational time ($<0.02\text{ s}$).

```latex
\begin{table*}[t]
\caption{Computational scaling of 3D dynamic voxelization and Fortran unformatted binary stream (.bdf) export across simulation grid resolutions ($\Delta x$) for 4,951,646 raw TLS points in a 40 $\times$ 40 $\text{m}^2$ Pinus ponderosa stand ($N = 3$ repeats, mean $\pm$ std).}
\label{tab:voxel_scaling}
\centering
\small
\begin{tabular}{ccccccc}
\hline
\textbf{Grid Cell Size} & \textbf{Active Voxels} & \textbf{Voxelization} & \textbf{BDF Stream} & \textbf{BDF Throughput} & \textbf{BDF Bandwidth} & \textbf{Total Pipeline} \\
$\Delta x$ (m) & $N_{\text{vox}}$ & Time (s) & Write Time (ms) & ($10^6$ vox/s) & (MB/s) & Time (s) \\
\hline
1.00 & 1,573 & $0.279 \pm 0.010$ & $5.32 \pm 0.91$ & 0.30 & 13.6 & $0.287 \pm 0.010$ \\
0.50 & 8,031 & $0.270 \pm 0.016$ & $4.17 \pm 0.73$ & 1.92 & 88.2 & $0.276 \pm 0.017$ \\
0.30 & 26,306 & $0.272 \pm 0.012$ & $6.03 \pm 0.94$ & 4.37 & 199.9 & $0.281 \pm 0.012$ \\
0.25 & 40,303 & $0.262 \pm 0.018$ & $6.08 \pm 0.54$ & 6.63 & 303.6 & $0.271 \pm 0.017$ \\
0.20 & 67,002 & $0.282 \pm 0.028$ & $7.71 \pm 0.63$ & 8.69 & 397.6 & $0.293 \pm 0.027$ \\
0.15 & 128,173 & $0.294 \pm 0.021$ & $11.33 \pm 1.00$ & 11.32 & 518.1 & $0.311 \pm 0.020$ \\
0.10 & 303,365 & $0.276 \pm 0.012$ & $20.94 \pm 0.13$ & 14.49 & 663.1 & $0.307 \pm 0.013$ \\
\hline
\end{tabular}
\end{table*}
```

The unformatted Fortran sequential binary stream writer (`.bdf`) demonstrated exceptional throughput (**Figure 3(b)**). By pre-allocating an interleaved structured NumPy record array conforming exactly to FDS unformatted record header specifications ($48\text{ bytes per voxel}$: 4-byte leading length tags, 24-byte double-precision coordinates $[x, y, z]$, 4-byte trailing length tags, and 8-byte double-precision bulk density $\rho_b$), `TLS_to_FDS` flushes the entire spatial matrix in a single direct system `write()` call. 

Streaming throughput scaled asymptotically from **$1.92 \times 10^6\text{ voxels/s}$** ($88.2\text{ MB/s}$) at 8,031 cells to **$14.49 \times 10^6\text{ voxels/s}$** (**$663.1\text{ MB/s}$**) at 303,365 cells, requiring only **$20.94\text{ ms}$** of wall-clock time for over 300,000 cells. This memory streaming efficiency ensures that file export overhead remains functionally imperceptible to the user.

---

### 3.3 1D Boundary Fuel Model (BFM) Discretization and Vent Compression

In physics-based fire modeling, surface litter and duff fuel beds are modeled as 1D boundary fuels interacting with the ground surface (`Z = 0`) via FDS `&VENT` namelists. A known computational challenge when mapping continuous forest floor bulk density fields into FDS is namelist syntax bloat: defining individual vents for every surface grid cell creates massive text input decks (hundreds of thousands of lines) that dramatically degrade FDS startup parsing speed and exhaust MPI process memory.

`TLS_to_FDS` addresses this problem through **continuous litter quantization** followed by **adjacent-cell row merging** (**Figure 3(c)**, **Table 2**):
1. **Model 1 (Stem Distance Decay)**: Evaluates nearest-neighbor Euclidean distance decay from stem coordinates. The 2D scalar field across 40,000 ground cells ($\Delta x = 0.20\text{ m}$) is computed in less than **$1.0\text{ ms}$** ($0.91\text{--}1.12\text{ ms}$).
2. **Model 2 (Canopy Turnover with 2D Gaussian Wind Dispersion)**: Projects the overhead 3D canopy point cloud into a 2D vertical mass projection, applies Olson exponential accumulation/decomposition, and performs isotropic 2D Gaussian spatial smoothing ($\sigma = 1.5\text{ m}$). The spatial convolution across the grid executes in **$6.8\text{--}8.2\text{ ms}$**.

```latex
\begin{table*}[t]
\caption{Ground fuel Boundary Fuel Model (BFM) computation time and row-merging vent compression efficiency across discrete quantization bins ($N_{\text{bins}} \in [2, 100]$) on a 40 $\times$ 40 $\text{m}^2$ plot at $\Delta x = 0.20\text{ m}$ (40,000 raw surface cells).}
\label{tab:litter_scaling}
\centering
\small
\begin{tabular}{lcccccc}
\hline
\textbf{Litter Model Formulation} & \textbf{Bins} & \textbf{Field Time} & \textbf{Tiling Time} & \textbf{Total Time} & \textbf{Generated} & \textbf{Vent Compression} \\
& $N_{\text{bins}}$ & (ms) & (ms) & (ms) & \textbf{VENT Patches} & \textbf{Efficiency (\%)} \\
\hline
\textbf{Model 1 (Distance Decay)} & 2 & 1.12 & 0.90 & 2.02 & 45 & \textbf{99.89\%} \\
& 5 & 0.96 & 1.17 & 2.13 & 150 & \textbf{99.62\%} \\
& 10 & 0.98 & 1.16 & 2.14 & 328 & \textbf{99.18\%} \\
& 20 & 0.96 & 1.40 & 2.36 & 587 & \textbf{98.53\%} \\
& 50 & 0.96 & 1.78 & 2.74 & 1,050 & \textbf{97.38\%} \\
& 100 & 0.99 & 2.28 & 3.27 & 1,554 & \textbf{96.11\%} \\
\hline
\textbf{Model 2 (Canopy Turnover + Wind)} & 2 & 8.22 & 1.10 & 9.32 & 136 & \textbf{99.66\%} \\
& 5 & 7.74 & 1.36 & 9.10 & 388 & \textbf{99.03\%} \\
& 10 & 7.32 & 1.49 & 8.81 & 730 & \textbf{98.18\%} \\
& 20 & 6.90 & 2.13 & 9.03 & 1,349 & \textbf{96.63\%} \\
& 50 & 6.91 & 3.33 & 10.24 & 2,703 & \textbf{93.24\%} \\
& 100 & 7.10 & 4.05 & 11.14 & 4,003 & \textbf{89.99\%} \\
\hline
\end{tabular}
\end{table*}
```

Once quantized into $N_{\text{bins}}$, contiguous cells along horizontal grid rows sharing identical density bins are merged into single rectangular bounding vents (`XB = X1, X2, Y1, Y2, 0, 0`). Even at fine quantization ($N_{\text{bins}} = 100$), row merging compresses 40,000 raw ground cells down to **1,554 vents in Model 1** (**$96.1\%$ reduction**) and **4,003 vents in Model 2** (**$90.0\%$ reduction**). At the default configuration ($N_{\text{bins}} = 10$), compression efficiency exceeds **$98.2\%\text{ to }99.2\%$** (328 to 730 vents), keeping generated `.fds` script files compact ($<4.3\text{ KB}$) and ensuring immediate parsing by the FDS Fortran runtime.

---

### 3.4 Full End-to-End Execution Budget

To contextualize the pipeline's operational efficiency, **Figure 3(d)** and **Table 3** present the complete stage-by-stage wall-clock computational budget under default simulation parameters ($\Delta x = 0.20\text{ m}$, 67,002 3D voxels, Model 2 canopy turnover ground fuels with $N_{\text{bins}} = 10$ on 40,000 surface cells):

```latex
\begin{table}[h]
\caption{Stage-by-stage computational runtime budget for full domain conversion under default settings ($\Delta x = 0.20\text{ m}$, 4,951,646 raw TLS points, 67,002 voxels).}
\label{tab:runtime_budget}
\centering
\small
\begin{tabular}{lccc}
\hline
\textbf{Pipeline Stage} & \textbf{Execution Time (s)} & \textbf{Budget (\%)} & \textbf{Computational Complexity} \\
\hline
Point Cloud Ingestion (.laz) & 0.434 & 61.8\% & $\mathcal{O}(N_{\text{pts}})$ C++ decompressor streaming \\
3D Dynamic Voxelization & 0.240 & 34.1\% & $\mathcal{O}(N_{\text{pts}})$ Spatial micro-hashing ($\delta = 1\text{ cm}$) \\
Fortran .bdf Stream Write & 0.007 & 1.0\% & $\mathcal{O}(N_{\text{vox}})$ Zero-copy structured I/O \\
Litter BFM Discretization & 0.020 & 2.8\% & $\mathcal{O}(N_{\text{cells}})$ 2D Gaussian FFT \& run-length merge \\
FDS Master Script Assembly & 0.002 & 0.3\% & $\mathcal{O}(N_{\text{vents}} + N_{\text{mesh}})$ String templating \\
\hline
\textbf{Total Conversion Time} & \textbf{0.703} & \textbf{100.0\%} & \textbf{Domain Ready for FDS Simulation} \\
\hline
\end{tabular}
\end{table}
```

The entire end-to-end conversion of nearly **5 million raw TLS points** into a fully partitioned, physics-ready FDS scenario completes in **$0.703\text{ seconds}$**. The computational profile is overwhelmingly dominated by disk I/O and point decompression ($61.8\%$), followed by 1 cm spatial micro-voxelization ($34.1\%$). All downstream numerical operations—including Fortran binary stream creation, 2D Gaussian wind dispersion, row-merging vent tiling, and master `.fds` namelist script generation—consume less than **$4.1\%$ combined** ($0.029\text{ s}$).

```
========================================================================================
FIGURE 3 CAPTION (COMPUTERS AND ELECTRONICS IN AGRICULTURE)
========================================================================================
Figure 3: Quantitative computational efficiency and scalability benchmarks of the TLS_to_FDS 
pipeline evaluated on 4,951,646 raw TLS returns from a 40 x 40 m^2 Pinus ponderosa stand 
(Sycan Marsh, Oregon). (a) Active 3D voxel count (log scale) and execution time as a function 
of simulation grid cell resolution Delta x in [0.10, 1.00] m, demonstrating algorithmic 
invariance of Stage 1 spatial micro-hashing. (b) Fortran unformatted binary stream (.bdf) export 
time and zero-copy streaming throughput reaching 14.49 million voxels/second (663 MB/s). 
(c) 1D Boundary Fuel Model (BFM) runtime and generated &VENT ground patch counts across 
discretization bins N_bins in [2, 100], showing 90.0% to 99.9% vent reduction via adjacent-cell 
row merging. (d) Computational time Budget (Default settings, Delta x = 0.20 m, total conversion 
time = 0.703 s).
========================================================================================
```

### 3.5 Discussion: Comparison with Traditional CFD Pre-Processing Workflows

Historically, preparing 3D vegetative fuel matrices from raw terrestrial LiDAR point clouds has required manual, multi-software pipelines (e.g., CloudCompare for clipping, external Python scripts for ray-tracing or grid accumulation, GIS tools for raster conversion, and custom text editors for FDS namelist assembly). Comprehensive ray-tracing algorithms (such as AMAPvox or VoxLOD; Béland et al., 2014; Pimont et al., 2018) provide rigorous Beer-Lambert optical transmittance inversion but require complete scanner station coordinates and pulse trajectory metadata, often taking tens of minutes to multiple hours to process plot-scale datasets.

In contrast, `TLS_to_FDS` provides a self-contained, sub-second execution pipeline ($<0.75\text{ s}$) that operates directly on standard classified point clouds without trajectory metadata dependencies. By decoupling spatial presence from point flux through two-stage micro-voxelization and enforcing strict analytical mass conservation ($\gamma_{\text{mass}}$), the software provides fire behavior modelers with a fast, repeatable, and computationally rigorous tool for setting up large-scale CFD wildland fire simulations.
