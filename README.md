# TLS-to-FDS: Terrestrial LiDAR Voxelization for Wildfire Simulations

# WORK IN PROGRESS

This repository provides a modular, reproducible workflow to process Terrestrial Laser Scanning (TLS) forest point clouds and export them into structural inputs natively recognized by the **Fire Dynamics Simulator (FDS)**. 

The pipeline ingests stratified forest layers (e.g., ground, surface, canopy, stems), scales coordinates relative to a clean spatial origin $(0,0,0)$ to preserve CFD stability, spatial-voxelizes structural attributes, and outputs Fortran Binary Data Files (`.bdf`) alongside domain mesh definitions (`.fds`).

---

## Repository Structure

```text
TLS-to-FDS/
│
├── data/               # Input directory for stratified .laz files
├── output/             # Output target for generated .bdf and .fds configurations
├── config.yaml         # Project configuration (Voxel resolution, paths, Bulk Densities)
├── main.py             # Pipeline execution entry point
├── utils.py            # Computational helper functions 
└── requirements.txt    # Project Python dependencies
```

## Installation

1. Clone this repository to your computational environment.
2. Ensure you have Python 3.8+ deployed.
3. Install dependencies via pip:

```Bash
pip install -r requirements.txt
```

## Quick Start Guide

### Step 1: Obtain Test Data
You can download a testing dataset from the UKCEH Environmental Information Data Centre:

Download Link: [UKCEH Catalogue - Wildfire Fuel Test Data](https://catalogue.ceh.ac.uk/documents/467a735f-b03c-4c30-8781-82f0e11aec28)

This dataset includes five segmented point clouds in LAS format, representing different fuel classes from a forest plot. The forest plot consists of a 40 x 40 m Pinus ponderosa plot scanned with a Riegl-VZ400i in Sycan Marsh, Oregon, USA. 

* grass_crop.las: 3D point cloud that stores the fuel class “grass” present in the forest plot.
* shrub_crop.las: 3D point cloud that stores the fuel class “shrub” present in the forest plot.
* wood_crop.las: 3D point cloud that stores the fuel class “tree stem” present in the forest plot
* leaf_crop.las: 3D point cloud that stores the fuel class “tree branch+leaves” present in the forest plot.
* leaf_crop_high.las: 3D point cloud that stores the fuel class “tree branch+leaves” after applying a virtual treatment. The virtual treatment is pruning the branches under 3 meters (or leaving only those that are further than 3 meters from the ground level).


Unzip and place the assets inside the Local /data folder.

### Step 2: Configure System Settings
Modify config.yaml to specify your targeted voxel sizes and set corresponding bulk density metrics matching your environmental inventory baseline:

### Step 3: Run the Processing Pipeline
Execute the master process script from the root workspace directory:

```Bash
python python.py
```
Upon completion, look inside the /output directory for your binary files.

The testing dataset also contains three FDS input files detailing the configuration for three separate simulations. More details about these simulations are available at https://doi.org/10.5285/467a735f-b03c-4c30-8781-82f0e11aec28.

## TODO

* Check if it is necessary to expand simulation domain to include litter+duff boundary models
* Add tooltips to each preset so that it displays other fuel properties (e.g., SV ratio)
* Add figure with fuel layers
* Add "About" table

## Planned Updates

* Add more presets
* Add blank preset where user can set values for each fuel property
* Add dynamic bulk density correction based on points-per-voxel / mean-points-per-class ratio
* ✅ Add litter / duff layers
* Integration of lateral/top domain buffer regions for stable atmospheric boundaries.
* ✅ Add output: log out with command to run FDS simulation
* Option to directly process point cloud with 3DFoS, so it only takes one single input file. 
* Dynamic multi-mesh MPI parallel allocation partitioning.
* Spatial overlapping checking logic to prevent localized bulk density inflation.