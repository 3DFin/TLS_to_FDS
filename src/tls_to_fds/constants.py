WELCOME_BANNER = """
====================================================================
🌲  TLS_to_FDS : Point Cloud to Fire Simulation Tool  🔥
====================================================================

Quick Start Guide:
1. Select your Input Directory (contains segmented .las/.laz).
2. Set your Output Directory (destination for .fds and .bdf files).
3. Set a Voxel Size (smaller = more detail, but longer simulation times).
4. Select a Forest Preset to load default combustion properties.
5. Add your fuel layers to the table and assign their classes.
6. Configure your wind and ignition parameters in the Simulation tab.
7. Click 'Generate FDS Files' to build the computational domain.

System initialized and standing by...
====================================================================
"""

# Mapping widget objectNames to their HTML formatted tooltip strings
TOOLTIPS = {
    # --- Basic Project Setup ---
    "line_input_dir": "<b>Input Directory</b><hr><p>Select the folder containing your segmented <code>.las</code> or <code>.laz</code> point cloud files.</p>",
    "line_output_dir": "<b>Output Directory</b><hr><p>Select the folder where the generated FDS (<code>.fds</code>) and Fortran Binary Data (<code>.bdf</code>) files will be saved.</p>",
    "spin_voxel_size": "<b>Voxel Size (m)</b><hr><p>Sets the 3D spatial resolution of the computational mesh.</p><ul><li><i>Smaller values</i> = Higher structural detail, but exponentially longer simulation times.</li><li><i>Larger values</i> = Faster simulations, but may homogenize fine fuel structures.</li></ul>",
    "combo_preset": "<b>Forest Preset</b><hr><p>Select a biome to automatically populate default combustion properties (Bulk Density, Moisture, S/V ratio, Particle length, Drag) for the fuel layers.</p>",
    
    # --- Ground Fuels (Litter / Duff) ---
    "check_litter_active": "<b>Enable Litter Layer</b><hr><p>Toggles the inclusion of a ground litter layer using a 1D Boundary Fuel Model (BFM) represented via surface <code>&SURF</code> and <code>&VENT</code> tiles.</p>",
    "combo_litter_mode": "<b>Litter Model Mode</b><hr><p>Select how spatial litter distribution is calculated:</p><ul><li><b>Uniform:</b> Homogeneous load across the domain.</li><li><b>Model 1 (Tree Distance):</b> Exponential decay from stem locations.</li><li><b>Model 2 (Canopy Turnover):</b> Vertical integration of overhead canopy point counts with 2D Gaussian wind dispersion.</li></ul>",
    "spin_litter_depth": "<b>Litter Layer Depth (m)</b><hr><p>Physical thickness of the surface fuel bed (default: 0.05 m).</p>",
    "spin_litter_bd": "<b>Litter Bulk Density (kg/m³)</b><hr><p>Nominal dry bulk density of the ground litter bed.</p>",
    "spin_litter_moisture": "<b>Litter Moisture Fraction</b><hr><p>Moisture content of the litter layer as a dry-weight fraction (e.g. 0.10 = 10%).</p>",
    "spin_num_litter_bins": "<b>Number of Litter Bulk Density Bins</b><hr><p>Number of discrete bulk density classes used to bin continuous spatial litter density maps into FDS <code>&SURF</code> definitions and row-merged <code>&VENT</code> patches.</p>",
    "line_tree_map": "<b>Tree Map CSV Path</b><hr><p>File path to tree stem coordinates (CSV/TXT with x,y columns) used by Model 1 for distance decay calculations.</p>",
    "spin_decay_alpha": "<b>Radial Decay Rate (α)</b><hr><p>Exponential decay coefficient controlling how rapidly litter density decreases with distance from tree stems in Model 1.</p>",
    "spin_min_litter_bd": "<b>Minimum Litter Bulk Density (kg/m³)</b><hr><p>Baseline background bulk density applied far away from tree stems in Model 1.</p>",
    "spin_turnover_rate": "<b>Canopy Turnover Rate (yr⁻¹)</b><hr><p>Annual fraction of overhead foliage/branch biomass shed as litter in Model 2 (e.g. 0.20 = 20%/yr).</p>",
    "spin_accumulation_years": "<b>Litter Accumulation Time (years)</b><hr><p>Number of years of unburned litter accumulation in Model 2.</p>",
    "spin_dispersion_sigma": "<b>Gaussian Dispersion Sigma (m)</b><hr><p>Standard deviation (meters) of the 2D Gaussian kernel modeling wind dispersion of falling canopy litter in Model 2.</p>",
    "line_dtm_path": "<b>DTM File Path</b><hr><p>Optional Digital Terrain Model point cloud or raster used for ground surface elevation referencing.</p>",

    # --- Simulation Timing & Wind ---
    "spin_sim_time": "<b>Total Simulation Time (s)</b><hr><p>The total duration the fire simulation will run in FDS.</p>",
    "spin_wind_dev": "<b>Wind Development Time (s)</b><hr><p>Pre-ignition time allowed for the wind field to fully stabilize and traverse across the domain before the fire starts.</p>",
    "spin_wind_dir": "<b>Wind Direction (Degrees)</b><hr><p>Meteorological wind direction:</p><ul><li><b>0º:</b> North</li><li><b>90º:</b> East</li><li><b>180º:</b> South</li><li><b>270º:</b> West</li></ul>",
    "spin_wind_speed": "<b>Wind Speed (m/s)</b><hr><p>Initial wind speed applied to the computational domain boundaries.</p>",
    # --- Ignition ---
    "spin_hrrpua": "<b>Heat Release Rate Per Unit Area</b><hr><p>Initial thermal intensity (kW/m²) for the ignition boundary. Used to kickstart the fire.</p>",
    "spin_ign_duration": "<b>Ignition Duration (s)</b><hr><p>How long the artificial ignition line remains active at peak HRRPUA before ramping down.</p>",
    "spin_vent_width": "<b>Ignition Width (m)</b><hr><p>Sets the physical width (or diameter) of the initial ignition vent.</p>",
    # --- Advanced Atmospheric & Ember Physics ---
    "spin_obukhov": """<b>Obukhov Length (L)</b><hr>
<p>Characterizes atmospheric thermal stability in Monin-Obukhov boundary layer theory.</p>
<ul>
    <li><b>Negative (L < 0):</b> Unstable stratification (enhanced convective turbulence).</li>
    <li><b>Positive (L > 0):</b> Stable stratification (suppressed turbulence).</li>
    <li><b>-500 m or ∞:</b> Neutrally stratified atmosphere (default).</li>
</ul>""",
    "spin_z0": """<b>Aerodynamic Roughness Length (z<sub>0</sub>)</b><hr>
<p>A theoretical measurement of how much a specific type of ground drags the wind. Specifically, it is the height above the ground where this surface friction causes the wind speed to drop to absolutely zero.</p>
<p>The rougher the surface, the higher up you have to go before you stop feeling the ground's dragging effect. According to the Davenport-Wieringa classification:</p>
<ul>
    <li><b>0.03 m:</b> Grass prairies / open fields</li>
    <li><b>0.25 m:</b> Scattered trees / vineyards</li>
    <li><b>0.5 m:</b> Forest stands / clumps (default)</li>
    <li><b>1.0 m:</b> Closed dense forests</li>
</ul>""",
    "check_track_embers": "<b>Enable Ember Transport</b><hr><p>Activates Lagrangian particle ember generation and automatically applies realistic char (180 kg/m³) and ash (50 kg/m³) density overrides (Mell et al. 2026).</p>",
    "spin_ember_density": "<b>Ember Density Threshold (kg/m³)</b><hr><p>Density at which decaying wood converts into loftable char embers.</p>",
    "spin_ember_velocity": "<b>Ember Velocity Threshold (m/s)</b><hr><p>Minimum local updraft wind velocity required to lift char embers into the plume flow.</p>",
    
    # --- Spatial Domain & MPI Partitioning ---
    "spin_pad_x": "<b>X Domain Padding (m)</b><hr><p>Lateral domain padding added around the vegetation bounding box along the X axis.</p>",
    "spin_pad_y": "<b>Y Domain Padding (m)</b><hr><p>Inflow/outflow domain padding added around the vegetation bounding box along the Y axis.</p>",
    "spin_pad_z": "<b>Z Sky Padding (m)</b><hr><p>Height of coarse sky mesh placed above the forest canopy (enforces Zmax ≥ 5 × Hcanopy to prevent top boundary reflection).</p>",
    "spin_mpi_x": "<b>MPI X Subdivisions</b><hr><p>Number of parallel MPI domain mesh partitions along the X axis.</p>",
    "spin_mpi_y": "<b>MPI Y Subdivisions</b><hr><p>Number of parallel MPI domain mesh partitions along the Y axis.</p>",
    "btn_domain_wizard": "<b>Domain Geometry Wizard</b><hr><p>Opens an interactive calculator to optimize domain padding and multi-mesh MPI bounds based on total cell counts.</p>",

    # --- Diagnostics & Output Control ---
    "check_out_hrrpua": "<b>HRRPUA (Boundary File)</b><hr><p>Outputs a 2D map of Surface Heat Release Rate (kW/m²) for post-processing Rate of Spread and fireline intensity.</p>",
    "check_out_flame": "<b>Volumetric HRR (Slice)</b><hr><p>Outputs mid-plane 2D slices of HRRPUV (kW/m³) to visualize 3D flame volume and flame height.</p>",
    "check_out_temp": "<b>Gas Temperature (Slice)</b><hr><p>Outputs 2D gas temperature slices (°C) for analyzing plume convection and crown scorch height.</p>",
    "check_out_wind": "<b>Wind Velocity (Slice)</b><hr><p>Outputs U/W wind velocity vector slices (m/s) to evaluate wind-fire coupling and fire-induced indrafts.</p>",
    "check_out_biomass": "<b>Dry Biomass Tracking</b><hr><p>Tracks total dry fuel mass (kg) remaining in each vegetation layer over time to calculate % consumption.</p>",
    "check_ros_tracking": "<b>Enable Rate of Spread (RoS) Trackers</b><hr><p>Generates 4 transverse <code>&DEVC</code> lines measuring <code>MAXLOC X</code> / <code>MAXLOC Y</code> temperature statistics across domain span transects (20%, 40%, 60%, 80%) to track fire front progress.</p>",
    "line_slice_heights": "<b>Slice Heights (m)</b><hr><p>Comma-separated list of horizontal elevation heights (e.g. 0.5, 1.5, 2.5) for multi-level <code>&SLCF</code> slice planes.</p>",
    "check_restart_active": "<b>Enable Simulation Restarts</b><hr><p>Activates FDS restart checkpoint generation (<code>&DUMP DT_RESTART</code>) allowing simulations to be paused and resumed.</p>",
    "spin_dt_restart": "<b>Restart Checkpoint Interval (s)</b><hr><p>Time interval in seconds between simulation restart checkpoint saves.</p>",
    "spin_dt_hrr": "<b>HRR Output Interval (s)</b><hr><p>Time interval in seconds for writing global Heat Release Rate output curves.</p>",
    "spin_dt_devc": "<b>Device Output Interval (s)</b><hr><p>Time interval in seconds for logging device (<code>&DEVC</code>) time history data.</p>",
    "spin_dt_part": "<b>Particle Output Interval (s)</b><hr><p>Time interval in seconds for exporting Lagrangian ember particle tracking visualization files.</p>",
}

