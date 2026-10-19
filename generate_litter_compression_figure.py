"""Publication Figure: 1D Boundary Fuel Model (BFM) Discretization, Quantization Binning,
and 2D Scanline Row-Merge Compression Workflow.

Generates Figure 4 for Computers and Electronics in Agriculture (COMPAG, Elsevier).
Outputs:
  - assets/fig_litter_patch_compression.png (300 DPI raster)
  - assets/fig_litter_patch_compression.pdf (Vector publication format)
"""

from pathlib import Path

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm, ListedColormap

# Ensure output directories exist
assets_dir = Path("assets")
assets_dir.mkdir(parents=True, exist_ok=True)

# Publication typography & aesthetics
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 8.8,
        "axes.labelsize": 9.5,
        "axes.titlesize": 10.2,
        "xtick.labelsize": 8.0,
        "ytick.labelsize": 8.0,
        "figure.titlesize": 12.0,
    }
)

# Domain dimensions (10 m x 10 m representative plot)
plot_size = 10.0
nx, ny = 20, 20
dx, dy = plot_size / nx, plot_size / ny

# High-resolution coordinates for continuous field
hr_res = 300
x_hr = np.linspace(0, plot_size, hr_res)
y_hr = np.linspace(0, plot_size, hr_res)
X_hr, Y_hr = np.meshgrid(x_hr, y_hr)

# Discrete grid cell coordinates (cell centers)
x_cell = (np.arange(nx) + 0.5) * dx
y_cell = (np.arange(ny) + 0.5) * dy
X_cell, Y_cell = np.meshgrid(x_cell, y_cell)

# Tree stem locations, crown radii, and fuel loading weights
trees = [
    {"pos": (3.2, 6.8), "radius": 1.7, "weight": 19.5, "sigma": 1.5, "name": "Tree 1"},
    {"pos": (7.4, 6.2), "radius": 2.1, "weight": 22.0, "sigma": 1.8, "name": "Tree 2"},
    {"pos": (4.6, 2.7), "radius": 1.5, "weight": 17.0, "sigma": 1.4, "name": "Tree 3"},
]

# Prevailing wind drift vector (towards North-East, 45 deg)
wind_dx, wind_dy = 0.45, 0.35


def compute_litter_field(X, Y):
    """Computes realistic Model 2 canopy turnover & wind-dispersed litter field (kg/m3)."""
    base_litter = 2.0  # background open-area duff/litter
    field = np.full_like(X, base_litter)
    for t in trees:
        sx, sy = t["pos"]
        # Downwind shifted deposition center
        center_x = sx + wind_dx
        center_y = sy + wind_dy
        dist_sq = (X - center_x) ** 2 + (Y - center_y) ** 2
        field += t["weight"] * np.exp(-dist_sq / (2.0 * (t["sigma"] ** 2)))
    return field


field_hr = compute_litter_field(X_hr, Y_hr)
field_cells = compute_litter_field(X_cell, Y_cell)

vmin, vmax = 2.0, 24.0

# -------------------------------------------------------------
# Quantization Binning Setup (N_bins = 5)
# -------------------------------------------------------------
n_bins = 5
bin_edges = np.linspace(vmin, vmax, n_bins + 1)
bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
bin_colors = ["#fef0d9", "#fdcc8a", "#fc8d59", "#e34a33", "#b30000"]  # YlOrRd gradient
discrete_cmap = ListedColormap(bin_colors)
discrete_norm = BoundaryNorm(bin_edges, n_bins)

# Discretize cell values to bin indices (1 to 5)
cell_bin_idx = np.clip(np.digitize(field_cells, bin_edges[1:-1]) + 1, 1, n_bins)
# Map to bin center bulk density values so BoundaryNorm colors them correctly
field_quantized = bin_centers[cell_bin_idx - 1]

# -------------------------------------------------------------
# 2D Scanline Coalescing Algorithm (exact TLS_to_FDS logic)
# -------------------------------------------------------------
x_bounds = np.arange(nx + 1) * dx
y_bounds = np.arange(ny + 1) * dy

vents = []
active_rects = {}

for j in range(ny):
    row = cell_bin_idx[j]
    current_row_runs = {}
    i = 0
    while i < nx:
        b = row[i]
        start_i = i
        while i < nx and row[i] == b:
            i += 1
        current_row_runs[(start_i, i, b)] = j

    next_active_rects = {}
    for key, s_j in active_rects.items():
        if key in current_row_runs:
            next_active_rects[key] = s_j
            del current_row_runs[key]
        else:
            s_i, e_i, b = key
            vents.append(
                {
                    "xb": [x_bounds[s_i], x_bounds[e_i], y_bounds[s_j], y_bounds[j]],
                    "bin": b,
                    "n_cells": (e_i - s_i) * (j - s_j),
                }
            )
    next_active_rects.update(current_row_runs)
    active_rects = next_active_rects

for (s_i, e_i, b), s_j in active_rects.items():
    vents.append(
        {
            "xb": [x_bounds[s_i], x_bounds[e_i], y_bounds[s_j], y_bounds[ny]],
            "bin": b,
            "n_cells": (e_i - s_i) * (ny - s_j),
        }
    )

num_raw_cells = nx * ny
num_vents = len(vents)
compression_pct = (1.0 - num_vents / num_raw_cells) * 100.0

# =============================================================
# FIGURE CREATION: 4-PANEL HORIZONTAL PIPELINE
# =============================================================
fig, axes = plt.subplots(1, 4, figsize=(21.0, 5.0), dpi=300)
fig.subplots_adjust(wspace=0.30, top=0.84, bottom=0.12, left=0.035, right=0.965)

# -------------------------------------------------------------
# Panel (a): Continuous Spatial Litter Distribution Field
# -------------------------------------------------------------
ax1 = axes[0]
ax1.set_title(
    "(a) Continuous Ground Litter Field $\\rho_{\\mathrm{litter}}(x,y)$",
    fontweight="bold",
    pad=8,
)
im1 = ax1.imshow(
    field_hr,
    extent=[0, plot_size, 0, plot_size],
    origin="lower",
    cmap="YlOrBr",
    vmin=vmin,
    vmax=vmax,
    interpolation="bicubic",
)

# Overlay canopy crown perimeters and boles
for t in trees:
    sx, sy = t["pos"]
    crown = plt.Circle(
        (sx, sy),
        t["radius"],
        color="#2e7d32",
        fill=False,
        linestyle="--",
        linewidth=1.4,
        alpha=0.9,
    )
    ax1.add_patch(crown)
    ax1.plot(
        sx,
        sy,
        "o",
        color="#4e342e",
        markersize=6.5,
        markeredgecolor="white",
        markeredgewidth=1.2,
        zorder=5,
    )
    ax1.text(
        sx,
        sy - 0.5,
        t["name"],
        color="#2e7d32",
        fontsize=7.8,
        fontweight="bold",
        ha="center",
    )

# Prevailing wind indicator
ax1.annotate(
    "Wind Drift\n$U_{\\mathrm{ref}} = 3.5\\,\\mathrm{m/s}$",
    xy=(1.8, 1.8),
    xytext=(0.6, 0.7),
    arrowprops=dict(
        facecolor="#1565c0", edgecolor="white", width=2.0, headwidth=6.0, shrink=0.05
    ),
    fontsize=7.5,
    fontweight="bold",
    color="#0d47a1",
    bbox=dict(
        boxstyle="round,pad=0.25", facecolor="#e3f2fd", edgecolor="#90caf9", alpha=0.92
    ),
)

ax1.set_xlabel("X (m)")
ax1.set_ylabel("Y (m)")
ax1.set_xlim(0, plot_size)
ax1.set_ylim(0, plot_size)
ax1.set_aspect("equal")

cbar1 = plt.colorbar(im1, ax=ax1, fraction=0.046, pad=0.04)
cbar1.set_label("Continuous Bulk Density (kg/m$^3$)", fontsize=8.2)

# Information box
ax1.text(
    0.04,
    0.96,
    "Model 2: Canopy Turnover\n+ 2D Gaussian Dispersion\nPlot: 10 m × 10 m",
    transform=ax1.transAxes,
    va="top",
    ha="left",
    fontsize=7.6,
    fontweight="bold",
    bbox=dict(
        boxstyle="round,pad=0.3", facecolor="white", edgecolor="#8d6e63", alpha=0.92
    ),
)

# -------------------------------------------------------------
# Panel (b): Uncompressed CFD Grid Discretization
# -------------------------------------------------------------
ax2 = axes[1]
ax2.set_title(
    "(b) Uncompressed CFD Grid ($N_{\\mathrm{cells}}$ Vents)", fontweight="bold", pad=8
)
im2 = ax2.imshow(
    field_cells,
    extent=[0, plot_size, 0, plot_size],
    origin="lower",
    cmap="YlOrBr",
    vmin=vmin,
    vmax=vmax,
    interpolation="nearest",
)

# Draw full grid lines for every cell
for gx in x_bounds:
    ax2.axvline(gx, color="white", linewidth=0.45, alpha=0.6)
for gy in y_bounds:
    ax2.axhline(gy, color="white", linewidth=0.45, alpha=0.6)

# Tree boles overlay & crown perimeters
for t in trees:
    sx, sy = t["pos"]
    crown = plt.Circle(
        (sx, sy),
        t["radius"],
        color="#2e7d32",
        fill=False,
        linestyle="--",
        linewidth=0.9,
        alpha=0.45,
    )
    ax2.add_patch(crown)
    ax2.plot(
        sx,
        sy,
        "o",
        color="#4e342e",
        markersize=5.0,
        markeredgecolor="white",
        markeredgewidth=1.0,
        zorder=5,
    )

ax2.set_xlabel("X (m)")
ax2.set_ylabel("Y (m)")
ax2.set_xlim(0, plot_size)
ax2.set_ylim(0, plot_size)
ax2.set_aspect("equal")

cbar2 = plt.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04)
cbar2.set_label("Cell Bulk Density (kg/m$^3$)", fontsize=8.2)

# Warning callout box
ax2.text(
    0.04,
    0.96,
    f"Grid Resolution: $\\Delta x = 0.50$ m\nTotal Cells: {num_raw_cells}\n"
    f"Without Compression:\n  → {num_raw_cells} Individual &VENTs\n"
    "[!] Parser Bloat & Memory Stall",
    transform=ax2.transAxes,
    va="top",
    ha="left",
    fontsize=7.4,
    fontweight="bold",
    color="#b71c1c",
    bbox=dict(
        boxstyle="round,pad=0.3", facecolor="#ffebee", edgecolor="#ef5350", alpha=0.95
    ),
)

# -------------------------------------------------------------
# Panel (c): Quantization Binning (N_bins Discrete Classes)
# -------------------------------------------------------------
ax3 = axes[2]
ax3.set_title(
    f"(c) Quantization Binning ($N_{{\\mathrm{{bins}}}} = {n_bins}$ Classes)",
    fontweight="bold",
    pad=8,
)
im3 = ax3.imshow(
    field_quantized,
    extent=[0, plot_size, 0, plot_size],
    origin="lower",
    cmap=discrete_cmap,
    norm=discrete_norm,
    interpolation="nearest",
)

# Grid lines
for gx in x_bounds:
    ax3.axvline(gx, color="white", linewidth=0.45, alpha=0.5)
for gy in y_bounds:
    ax3.axhline(gy, color="white", linewidth=0.45, alpha=0.5)

# Tree boles overlay & crown perimeters
for t in trees:
    sx, sy = t["pos"]
    crown = plt.Circle(
        (sx, sy),
        t["radius"],
        color="#2e7d32",
        fill=False,
        linestyle="--",
        linewidth=0.9,
        alpha=0.45,
    )
    ax3.add_patch(crown)
    ax3.plot(
        sx,
        sy,
        "o",
        color="#4e342e",
        markersize=5.0,
        markeredgecolor="white",
        markeredgewidth=1.0,
        zorder=5,
    )

ax3.set_xlabel("X (m)")
ax3.set_ylabel("Y (m)")
ax3.set_xlim(0, plot_size)
ax3.set_ylim(0, plot_size)
ax3.set_aspect("equal")

cbar3 = plt.colorbar(im3, ax=ax3, fraction=0.046, pad=0.04, ticks=bin_edges)
cbar3.set_label("Quantized Bulk Density Range (kg/m$^3$)", fontsize=8.2)
cbar3.ax.set_yticklabels([f"{v:.1f}" for v in bin_edges])

# Info callout box
ax3.text(
    0.04,
    0.96,
    f"Continuous → {n_bins} Discrete Bins\n"
    f"Bin 1: [{bin_edges[0]:.1f} - {bin_edges[1]:.1f}) kg/m³\n"
    f"Bin 3: [{bin_edges[2]:.1f} - {bin_edges[3]:.1f}) kg/m³\n"
    f"Bin 5: [{bin_edges[4]:.1f} - {bin_edges[5]:.1f}] kg/m³\n"
    "[OK] Generates 5 &SURF Definitions",
    transform=ax3.transAxes,
    va="top",
    ha="left",
    fontsize=7.4,
    fontweight="bold",
    color="#004d40",
    bbox=dict(
        boxstyle="round,pad=0.3", facecolor="#e0f2f1", edgecolor="#26a69a", alpha=0.95
    ),
)

# -------------------------------------------------------------
# Panel (d): 2D Scanline Coalesced Patches (VENT Compression)
# -------------------------------------------------------------
ax4 = axes[3]
ax4.set_title(
    f"(d) Scanline Row-Merge ({compression_pct:.1f}% Reduction)",
    fontweight="bold",
    pad=8,
)

# Background showing quantized field
im4 = ax4.imshow(
    field_quantized,
    extent=[0, plot_size, 0, plot_size],
    origin="lower",
    cmap=discrete_cmap,
    norm=discrete_norm,
    interpolation="nearest",
    alpha=0.82,
)

# Draw each merged rectangular vent patch with crisp black borders
for v in vents:
    x1, x2, y1, y2 = v["xb"]
    w = x2 - x1
    h = y2 - y1
    rect = patches.Rectangle(
        (x1, y1),
        w,
        h,
        linewidth=1.2,
        edgecolor="#212121",
        facecolor="none",
        zorder=4,
    )
    ax4.add_patch(rect)

# Highlight a prominent multi-cell merged patch (Bin 5 high-density patch: 24 cells)
sample_p = next(v for v in vents if v["n_cells"] == 24 and v["bin"] == 5)
sx1, sx2, sy1, sy2 = sample_p["xb"]
sm_rect = patches.Rectangle(
    (sx1, sy1),
    sx2 - sx1,
    sy2 - sy1,
    linewidth=2.4,
    edgecolor="#004d40",
    facecolor="#80cbc4",
    alpha=0.45,
    zorder=5,
)
ax4.add_patch(sm_rect)

# Clean, non-overlapping annotation in upper left pointing to the top of the patch
ax4.annotate(
    f"Merged &VENT (SURF_ID='SURF_L5'):\n"
    f"XB = {sx1:.1f}, {sx2:.1f}, {sy1:.1f}, {sy2:.1f}, 0.0, 0.0\n"
    f"→ {sample_p['n_cells']} cells (6.0m × 1.0m) = 1 &VENT line",
    xy=(4.2, 7.5),
    xytext=(0.4, 8.4),
    arrowprops=dict(
        facecolor="#004d40", edgecolor="white", width=1.6, headwidth=5.5, shrink=0.06
    ),
    fontsize=7.3,
    fontweight="bold",
    color="#004d40",
    bbox=dict(
        boxstyle="round,pad=0.28", facecolor="#e0f2f1", edgecolor="#00796b", alpha=0.96
    ),
    zorder=10,
)

# Tree boles overlay & crown perimeters
for t in trees:
    sx, sy = t["pos"]
    crown = plt.Circle(
        (sx, sy),
        t["radius"],
        color="#2e7d32",
        fill=False,
        linestyle="--",
        linewidth=0.9,
        alpha=0.45,
    )
    ax4.add_patch(crown)
    ax4.plot(
        sx,
        sy,
        "o",
        color="#4e342e",
        markersize=5.0,
        markeredgecolor="white",
        markeredgewidth=1.0,
        zorder=6,
    )

ax4.set_xlabel("X (m)")
ax4.set_ylabel("Y (m)")
ax4.set_xlim(0, plot_size)
ax4.set_ylim(0, plot_size)
ax4.set_aspect("equal")

cbar4 = plt.colorbar(im4, ax=ax4, fraction=0.046, pad=0.04, ticks=bin_centers)
cbar4.set_label("FDS &SURF Class ID", fontsize=8.2)
cbar4.ax.set_yticklabels([f"SURF_L{i}" for i in range(1, n_bins + 1)])

# Success summary box
ax4.text(
    0.04,
    0.04,
    f"Raw Cells: {num_raw_cells}\n"
    f"Merged Patches: {num_vents}\n"
    f"Compression: {compression_pct:.1f}%\n"
    "[OK] Fast FDS Ingestion & Zero Memory Stall",
    transform=ax4.transAxes,
    va="bottom",
    ha="left",
    fontsize=7.4,
    fontweight="bold",
    color="#1b5e20",
    bbox=dict(
        boxstyle="round,pad=0.3", facecolor="#e8f5e9", edgecolor="#4caf50", alpha=0.95
    ),
)

plt.suptitle(
    "Figure 4: 1D Boundary Fuel Model (BFM) Ground Fuel Discretization, Quantization Binning, and Patch Compression",
    fontweight="bold",
    y=0.98,
    fontsize=11.5,
)

# Save figures
png_out = assets_dir / "fig_litter_patch_compression.png"
pdf_out = assets_dir / "fig_litter_patch_compression.pdf"
plt.savefig(png_out, dpi=300, bbox_inches="tight")
plt.savefig(pdf_out, dpi=300, bbox_inches="tight")
plt.close(fig)

print("Figure 4 successfully generated and saved to:")
print(f"  -> PNG: {png_out.resolve()}")
print(f"  -> PDF: {pdf_out.resolve()}")
