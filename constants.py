# constants.py

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
    "spin_ign_duration": "Duration (in seconds) the ignition line remains active at peak HRRPUA.",
    "spin_obukhov": "Obukhov length (L). Negative values denote an unstable atmosphere. Default: -350 based on standard wildfire profiles.",
    "spin_z0": "Aerodynamic roughness length (z0). Default: 0.5 for rough landscapes.",
    "spin_ember_density": "Density threshold for ember generation. Default: 62.5 (per Ruddy Mell).",
    "spin_ember_velocity": "Velocity threshold for ember generation. Default: 0.0.",
    "spin_vent_width": "Sets the physical width (or diameter) of the initial ignition area in meters.",
    "check_out_hrrpua": "Outputs a 2D boundary file of the Heat Release Rate Per Unit Area. Crucial for post-processing Rate of Spread (RoS) and fireline intensity.",
    "check_out_flame": "Outputs a 2D slice of Volumetric Heat Release Rate (HRRPUV). Used to visualize the flame structure and calculate flame height.",
    "check_out_temp": "Outputs gas temperature slices. Useful for analyzing convective heat transfer, plume dynamics, and crown scorch heights.",
    "check_out_wind": "Outputs wind velocity vectors. Critical for analyzing wind-fire interactions, updrafts, and fire-induced weather.",
    "check_out_biomass": "Outputs the total mass (kg) of each fuel layer over time. Used to calculate fuel consumption and the percentage of burnt dry biomass."
}