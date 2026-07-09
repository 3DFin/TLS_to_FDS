WELCOME_BANNER = """
====================================================================
🌲  TLS_to_FDS : Point Cloud to Fire Simulation Tool  🔥
====================================================================
Welcome to the integration framework!

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

# Mapping widget objectNames to their tooltip strings
TOOLTIPS = {
    # --- Basic Project Setup ---
    "line_input_dir": "Select the folder containing your segmented .las or .laz point cloud files.",
    "line_output_dir": "Select the folder where the generated FDS (.fds) and Fortran Binary Data (.bdf) files will be saved.",
    "spin_voxel_size": "Sets the 3D resolution of the computational mesh. Smaller values = higher detail but exponentially longer simulation times.",
    "combo_preset": "Select the biome preset to automatically populate default combustion properties and bulk densities.",
    
    # --- Simulation Timing & Basic Wind ---
    "spin_sim_time": "Total time (in seconds) the fire simulation will run.",
    "spin_wind_dev": "Pre-ignition time allowed for the wind field to stabilize across the domain before the fire starts.",
    "spin_wind_dir": "Meteorological wind direction in degrees (0 = North, 90 = East, 180 = South, 270 = West).",
    "spin_wind_speed": "Initial wind speed applied to the domain boundary (m/s).",
    
    # --- Ignition ---
    "spin_hrrpua": "Initial Heat Release Rate Per Unit Area (kW/m²) for the ignition line.",
    "spin_ign_duration": "Duration (in seconds) the ignition line remains active at peak HRRPUA.",
    "spin_vent_width": "Sets the physical width (or diameter) of the initial ignition area in meters.",
    
    # --- Advanced Atmospheric & Ember Physics ---
    "spin_obukhov": """Obukhov length (L).
L characterizes the thermal stability of the atmosphere.
When L is negative, the atmosphere is unstably stratified; when positive, the atmosphere is stably stratified.
The stabilizing or destabilizing effects of stratification are strongest as L nears zero.
Accordingly, a neutrally stratified atmosphere would have an infinite Obukhov length.
Generally, an unstable atmosphere exhibits a decreasing temperature with height and relatively large fluctuations in wind direction/velocity.
Unstable atmospheres are strongly affected by the buoyancy-generated turbulence, resulting in enhanced mixing.
Conversely, highly stable atmospheric conditions suppress turbulent mixing.
Default: -350.""",

    "spin_z0": """Aerodynamic roughness length (z0).
It is a theoretical measurement of how much a specific type of ground drags the wind.
Specifically, it is the height above the ground where this surface friction causes the wind speed to drop to absolutely zero.
The rougher the surface, the higher up you have to go before you stop feeling the ground's dragging effect on the wind.
According to Davenport-Wieringa roughness length classification:
z0 = 0.0002 m (flat): Smooth surfaces (sea, paved areas, flat plains, etc.
z0 = 0.005 m (smooth): beach, pack ice, snow-covered fields
z0 = 0.03 m (open): grass prairies, farm fields, tundra
z0 = 0.1 m (roughly open): low crops and occasional obstacles (single bushes)
z0 = 0.25 m (rough): high crops, scattered trees or hedgerows, vineyards
z0 = 0.5 m (very rough): forest clumps, orchards, scattered buildings
z0 = 1.0 m (closed): forests, villages, suburbs
z0 = 2.0 m (chaotic): large towns and cities, irregular forests.
Default: 0.5 m.""",

    "spin_ember_density": """Density threshold for ember generation.
As a vegetative particle burns and converts to char its density decreases.
As the wood turns to char its structural integrity diminishes
and the drag forces may rip the vegetative element apart.
Default: 62.5.""",

    "spin_ember_velocity": """Velocity threshold for ember generation.
Char particles are subject to lofting by drag forces.
This phenomenon depends on the force exerted by the gas flow around the particle.
FDS uses a velocity threshold as a surrogate to the drag force, since this is more intuitive.
Default: 0.0.""",

    # --- Output Settings ---
    "check_out_hrrpua": "Outputs a 2D boundary file of the Heat Release Rate Per Unit Area. Crucial for post-processing Rate of Spread (RoS) and fireline intensity.",
    "check_out_flame": "Outputs a 2D slice of Volumetric Heat Release Rate (HRRPUV). Used to visualize the flame structure and calculate flame height.",
    "check_out_temp": "Outputs gas temperature slices. Useful for analyzing convective heat transfer, plume dynamics, and crown scorch heights.",
    "check_out_wind": "Outputs wind velocity vectors. Critical for analyzing wind-fire interactions, updrafts, and fire-induced weather.",
    "check_out_biomass": "Outputs the total mass (kg) of each fuel layer over time. Used to calculate fuel consumption and the percentage of burnt dry biomass."
}