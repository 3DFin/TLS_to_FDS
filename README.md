# TLS-to-FDS

**An open-source Python framework and GUI for converting semantically segmented 3D point clouds into Fire Dynamics Simulator (FDS) computational domains.**

---

### Overview
WRITE AN OVERVIEW

It automates the spatial discretization of `.las`/`.laz` files, dynamically assigns literature-based combustion properties, and generates ready-to-run `.fds` input files along with Fortran Binary Data Format (`.bdf`) voxel arrays.

### Key Features
* **Zero-Code GUI:** Built with PySide6, providing a fully tabbed, interactive interface for atmospheric parameterization, ground-fuel layer initialization, and FDS boundary condition setup.
* **Decoupled Science via Presets:** Combustion properties (bulk density, surface-to-volume ratio, moisture) are managed via external JSON presets, allowing easy customization for different biomes.
* **Advanced FDS Physics Integration:** Automatically configures multi-mesh MPI domains, 1D Boundary Fuel Models for synthetic surface litter/duff, and explicit Lagrangian firebrand/ember tracking.
* **Dynamic Spatial Ignition:** Automatically snaps ignition boundaries (point, line, or perimeter fires) to the exact geometric footprint of your processed point cloud.
* **High-Performance Voxelization:** Utilizes `dendroptimized` and `numpy` C-backends to process millions of LiDAR points in seconds without freezing the UI, thanks to multithreaded `QThread` workers.

### Installation & Requirements
WRITE INSTRUCTIONS FOR EXECUTABLE AND CLONING THE REPO / PYPI INSTALL

1. Clone this repository to your computational environment.
2. Ensure you have Python 3.8+ deployed.
3. Install dependencies via pip:

    ```Bash
    pip install -r requirements.txt
---
4. etc.

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

## Planned Updates

* Add more presets
* Add dynamic bulk density correction based on points-per-voxel / mean-points-per-class ratio
* Option to directly process point cloud with 3DFoS, so it only takes one single input file. 
* Dynamic multi-mesh MPI parallel allocation partitioning.