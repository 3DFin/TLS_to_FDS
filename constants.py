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
    
    # --- Simulation Timing & Basic Wind ---
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
<p>Characterizes the thermal stability of the lower atmosphere.</p>
<ul>
    <li><b>Negative (L < 0):</b> Unstable stratification (enhanced turbulent mixing).</li>
    <li><b>Positive (L > 0):</b> Stable stratification (suppressed mixing).</li>
    <li><b>Infinity:</b> Neutrally stratified atmosphere.</li>
</ul>
<span style="color: gray;"><i>Reference: FDS User Guide - Atmospheric Modeling.</i></span>""",

    "spin_z0": """<b>Aerodynamic Roughness Length (z<sub>0</sub>)</b><hr>
<p>A theoretical measurement of how much a specific type of ground drags the wind. Specifically, it is the height above the ground where this surface friction causes the wind speed to drop to absolutely zero.</p>
<p>The rougher the surface, the higher up you have to go before you stop feeling the ground's dragging effect. According to the Davenport-Wieringa classification:</p>
<ul>
    <li><b>0.0002 m (Flat):</b> Smooth surfaces (sea, paved areas, flat plains)</li>
    <li><b>0.005 m (Smooth):</b> Beach, pack ice, snow-covered fields</li>
    <li><b>0.03 m (Open):</b> Grass prairies, farm fields, tundra</li>
    <li><b>0.1 m (Roughly Open):</b> Low crops and occasional obstacles</li>
    <li><b>0.25 m (Rough):</b> High crops, scattered trees, vineyards</li>
    <li><b>0.5 m (Very Rough):</b> Forest clumps, orchards, scattered buildings</li>
    <li><b>1.0 m (Closed):</b> Forests, villages, suburbs</li>
    <li><b>2.0 m (Chaotic):</b> Large towns and cities, irregular forests</li>
</ul>
<span style="color: gray;"><i>Default: 0.5 m</i></span>""",

    "spin_ember_density": "<b>Ember Density Threshold (kg/m³)</b><hr><p>Density at which a vegetative particle converts to a loftable char particle. As wood turns to char, its structural integrity diminishes, allowing drag forces to rip it apart.</p>",
    "spin_ember_velocity": "<b>Ember Velocity Threshold (m/s)</b><hr><p>FDS uses a velocity threshold as a surrogate to drag force for lofting char particles. Sets the localized wind speed required to lift an ember.</p>",

    # --- Output Settings ---
    "check_out_hrrpua": "<b>HRRPUA (Boundary File)</b><hr><p>Outputs a 2D map of Surface Heat Release Rate. Crucial for post-processing Rate of Spread (RoS) and fireline intensity.</p>",
    "check_out_flame": "<b>Volumetric HRR (Slice)</b><hr><p>Outputs a mid-plane slice of HRRPUV. Used to visualize 3D flame structure and calculate flame height.</p>",
    "check_out_temp": "<b>Gas Temperature (Slice)</b><hr><p>Outputs thermal gas slices. Useful for analyzing convective heat transfer and crown scorch heights.</p>",
    "check_out_wind": "<b>Wind Velocity (Slice)</b><hr><p>Outputs U and W velocity vectors. Critical for analyzing wind-fire interactions and fire-induced updrafts.</p>",
    "check_out_biomass": "<b>Dry Biomass Tracking</b><hr><p>Outputs the total mass (kg) of each fuel layer over time to calculate fuel consumption and % burnt biomass.</p>"
}