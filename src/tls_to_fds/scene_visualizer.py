"""Pre-simulation 3D Scene Visualizer for TLS_to_FDS.

Generates pre-simulation diagnostic visualizations (interactive 3D HTML and 3D PNG summary)
showing voxelized fuel bulk density gradients, ignition boundary lines, 3D wind vector arrows,
and active preset metadata HUD overlays before submitting FDS jobs.
"""

import math
from pathlib import Path
from typing import Any, Optional, Union

import numpy as np


def compute_ignition_line_coords(
    ignition_boundary: Union[str, dict[str, Any]],
    forest_bounds: Union[tuple[float, ...], list[float]],
    vent_width: float = 1.0,
) -> tuple[np.ndarray, str]:
    """Calculates 3D spatial coordinates for rendering the ignition line or region."""
    fx_min, fy_min, fz_min, fx_max, fy_max, fz_max = forest_bounds[:6]
    z_ground = fz_min + 0.05  # Slight offset above ground for visibility

    ign_str = ""
    if isinstance(ignition_boundary, dict):
        ign_type = str(ignition_boundary.get("type", "Edge")).lower()
        ign_loc = str(
            ignition_boundary.get(
                "location",
                ignition_boundary.get(
                    "ign_pattern", ignition_boundary.get("pattern", "North Edge")
                ),
            )
        ).lower()
        ign_str = f"{ign_type} {ign_loc}".lower()
    elif isinstance(ignition_boundary, str):
        ign_str = ignition_boundary.lower()
    else:
        ign_str = "north edge"

    is_corner = "corner" in ign_str or "point" in ign_str

    # Compute 3D line vertices based on normalized ignition pattern
    if (
        is_corner
        or "south-west" in ign_str
        or "sw" in ign_str.split()
        or ("south" in ign_str and "west" in ign_str)
    ):
        if (
            ("south" in ign_str and "west" in ign_str)
            or "south-west" in ign_str
            or "sw" in ign_str.split()
        ):
            arm_x = min(fx_min + max(vent_width, (fx_max - fx_min) * 0.20), fx_max)
            arm_y = min(fy_min + max(vent_width, (fy_max - fy_min) * 0.20), fy_max)
            x_line = np.array([fx_min, fx_min, arm_x])
            y_line = np.array([arm_y, fy_min, fy_min])
            ign_label = "Ignition: SW Corner"
        elif (
            ("south" in ign_str and "east" in ign_str)
            or "south-east" in ign_str
            or "se" in ign_str.split()
        ):
            arm_x = max(fx_max - max(vent_width, (fx_max - fx_min) * 0.20), fx_min)
            arm_y = min(fy_min + max(vent_width, (fy_max - fy_min) * 0.20), fy_max)
            x_line = np.array([fx_max, fx_max, arm_x])
            y_line = np.array([arm_y, fy_min, fy_min])
            ign_label = "Ignition: SE Corner"
        elif (
            ("north" in ign_str and "west" in ign_str)
            or "north-west" in ign_str
            or "nw" in ign_str.split()
        ):
            arm_x = min(fx_min + max(vent_width, (fx_max - fx_min) * 0.20), fx_max)
            arm_y = max(fy_max - max(vent_width, (fy_max - fy_min) * 0.20), fy_min)
            x_line = np.array([fx_min, fx_min, arm_x])
            y_line = np.array([arm_y, fy_max, fy_max])
            ign_label = "Ignition: NW Corner"
        elif (
            ("north" in ign_str and "east" in ign_str)
            or "north-east" in ign_str
            or "ne" in ign_str.split()
        ):
            arm_x = max(fx_max - max(vent_width, (fx_max - fx_min) * 0.20), fx_min)
            arm_y = max(fy_max - max(vent_width, (fy_max - fy_min) * 0.20), fy_min)
            x_line = np.array([fx_max, fx_max, arm_x])
            y_line = np.array([arm_y, fy_max, fy_max])
            ign_label = "Ignition: NE Corner"
        else:
            x_line = np.array([fx_min, fx_max])
            y_line = np.array([fy_min, fy_min])
            ign_label = "Ignition: South Edge"
    elif "south" in ign_str or "y_min" in ign_str:
        x_line = np.array([fx_min, fx_max])
        y_line = np.array([fy_min, fy_min])
        ign_label = "Ignition: South Edge"
    elif "east" in ign_str or "x_max" in ign_str:
        x_line = np.array([fx_max, fx_max])
        y_line = np.array([fy_min, fy_max])
        ign_label = "Ignition: East Edge"
    elif "west" in ign_str or "x_min" in ign_str:
        x_line = np.array([fx_min, fx_min])
        y_line = np.array([fy_min, fy_max])
        ign_label = "Ignition: West Edge"
    elif "north" in ign_str or "y_max" in ign_str:
        x_line = np.array([fx_min, fx_max])
        y_line = np.array([fy_max, fy_max])
        ign_label = "Ignition: North Edge"
    elif "center" in ign_str or "centre" in ign_str:
        cx, cy = (fx_min + fx_max) / 2.0, (fy_min + fy_max) / 2.0
        hw = (fx_max - fx_min) * 0.15
        x_line = np.array([cx - hw, cx + hw])
        y_line = np.array([cy, cy])
        ign_label = "Ignition: Center"
    else:  # Default North Edge
        x_line = np.array([fx_min, fx_max])
        y_line = np.array([fy_max, fy_max])
        ign_label = "Ignition: North Edge"

    z_line = np.full_like(x_line, z_ground)
    return np.column_stack([x_line, y_line, z_line]), ign_label


def compute_ignition_vent_polygon(
    ignition_boundary: Union[str, dict[str, Any]],
    forest_bounds: Union[tuple[float, ...], list[float]],
    vent_width: float = 1.0,
) -> tuple[np.ndarray, str]:
    """Calculates 3D coordinates of the 2D ignition vent footprint patch at ground level."""
    fx_min, fy_min, fz_min, fx_max, fy_max, fz_max = forest_bounds[:6]
    z_ground = fz_min + 0.02
    w = max(0.2, vent_width)

    ign_pts, ign_label = compute_ignition_line_coords(
        ignition_boundary, forest_bounds, vent_width=w
    )

    ign_str = str(ignition_boundary).lower()
    is_corner = "corner" in ign_str or "point" in ign_str

    if (
        is_corner
        or "south-west" in ign_str
        or "sw" in ign_str.split()
        or ("south" in ign_str and "west" in ign_str)
    ):
        if (
            ("south" in ign_str and "west" in ign_str)
            or "south-west" in ign_str
            or "sw" in ign_str.split()
        ):
            xb = [fx_min, min(fx_min + w, fx_max), fy_min, min(fy_min + w, fy_max)]
        elif (
            ("south" in ign_str and "east" in ign_str)
            or "south-east" in ign_str
            or "se" in ign_str.split()
        ):
            xb = [max(fx_max - w, fx_min), fx_max, fy_min, min(fy_min + w, fy_max)]
        elif (
            ("north" in ign_str and "west" in ign_str)
            or "north-west" in ign_str
            or "nw" in ign_str.split()
        ):
            xb = [fx_min, min(fx_min + w, fx_max), max(fy_max - w, fy_min), fy_max]
        elif (
            ("north" in ign_str and "east" in ign_str)
            or "north-east" in ign_str
            or "ne" in ign_str.split()
        ):
            xb = [max(fx_max - w, fx_min), fx_max, max(fy_max - w, fy_min), fy_max]
        else:
            xb = [fx_min, fx_max, fy_min, min(fy_min + w, fy_max)]
    elif "south" in ign_str or "y_min" in ign_str:
        xb = [fx_min, fx_max, fy_min, min(fy_min + w, fy_max)]
    elif "east" in ign_str or "x_max" in ign_str:
        xb = [max(fx_max - w, fx_min), fx_max, fy_min, fy_max]
    elif "west" in ign_str or "x_min" in ign_str:
        xb = [fx_min, min(fx_min + w, fx_max), fy_min, fy_max]
    elif "north" in ign_str or "y_max" in ign_str:
        xb = [fx_min, fx_max, max(fy_max - w, fy_min), fy_max]
    elif "center" in ign_str or "centre" in ign_str:
        cx, cy = (fx_min + fx_max) / 2.0, (fy_min + fy_max) / 2.0
        hw = (fx_max - fx_min) * 0.15
        xb = [cx - hw, cx + hw, cy - w / 2.0, cy + w / 2.0]
    else:
        xb = [fx_min, fx_max, max(fy_max - w, fy_min), fy_max]

    poly_x = [xb[0], xb[1], xb[1], xb[0], xb[0]]
    poly_y = [xb[2], xb[2], xb[3], xb[3], xb[2]]
    poly_z = [z_ground, z_ground, z_ground, z_ground, z_ground]

    return np.column_stack([poly_x, poly_y, poly_z]), ign_label


def compute_wind_vector_arrow(
    wind_params: dict[str, Any],
    domain_bounds: Union[tuple[float, ...], list[float]],
) -> tuple[np.ndarray, np.ndarray, float, str]:
    """Calculates 3D origin and vector direction for rendering the wind arrow."""
    x_min, y_min, z_min, x_max, y_max, z_max = domain_bounds[:6]

    wind_speed = float(wind_params.get("wind_speed", wind_params.get("speed", 5.0)))
    wind_dir_deg = float(
        wind_params.get(
            "wind_dir",
            wind_params.get("wind_direction", wind_params.get("dir", 15.0)),
        )
    )  # Compass deg

    # Convert meteorological direction (direction FROM which wind blows) to vector direction (direction TO which wind flows)
    rad = math.radians(wind_dir_deg)
    u_vector = -math.sin(rad)
    v_vector = -math.cos(rad)

    # Scale vector length relative to domain width
    domain_span = max(x_max - x_min, y_max - y_min)
    arrow_len = domain_span * 0.18

    # Place arrow in top-right sky quadrant of domain
    arrow_start = np.array(
        [
            x_min + (x_max - x_min) * 0.85 - u_vector * arrow_len,
            y_min + (y_max - y_min) * 0.85 - v_vector * arrow_len,
            z_min + (z_max - z_min) * 0.85,
        ]
    )
    arrow_dir = np.array([u_vector * arrow_len, v_vector * arrow_len, 0.0])

    wind_label = f"Wind: {wind_speed:.1f} m/s ({wind_dir_deg:.0f}°)"
    return arrow_start, arrow_dir, wind_speed, wind_label


def render_3d_scene_matplotlib(
    file_path: Path,
    voxel_coords: np.ndarray,
    bulk_densities: np.ndarray,
    domain_bounds: Union[tuple[float, ...], list[float]],
    forest_bounds: Union[tuple[float, ...], list[float]],
    voxel_size: float,
    ignition_boundary: Union[str, dict[str, Any]],
    wind_params: dict[str, Any],
    preset_name: str = "Custom Preset",
    litter_2d: Optional[np.ndarray] = None,
) -> None:
    """Renders a styled static 3D summary figure (.png) of the simulation scene."""
    try:
        import matplotlib

        try:
            matplotlib.use("Agg")
        except Exception:
            pass
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection

        fig = plt.figure(figsize=(11, 8.5), dpi=300)
        ax = fig.add_subplot(111, projection="3d")
        ax.set_facecolor("#f8f9fa")

        # 1. Sub-sample voxels if count is large for fast rendering
        max_scatter_pts = 45000
        if len(voxel_coords) > max_scatter_pts:
            indices = np.random.choice(
                len(voxel_coords), size=max_scatter_pts, replace=False
            )
            pts = voxel_coords[indices]
            bds = bulk_densities[indices]
        else:
            pts = voxel_coords
            bds = bulk_densities

        # 2. Render Fuel Voxels colored by Bulk Density (YlOrRd colormap)
        if len(pts) > 0:
            sc = ax.scatter(
                pts[:, 0],
                pts[:, 1],
                pts[:, 2],
                c=bds,
                cmap="YlOrRd",
                s=math.ceil(voxel_size * 22.0),
                alpha=0.75,
                edgecolors="none",
            )
            cbar = fig.colorbar(
                sc,
                ax=ax,
                shrink=0.75,
                pad=0.08,
                aspect=20,
                label="Fuel Bulk Density (kg/m³)",
            )
            cbar.ax.tick_params(labelsize=9.5)

        # 2b. Render Flat 2D Ground Litter Layer (1D BFM) strictly on the Forest Floor
        if litter_2d is not None and np.any(litter_2d > 0):
            ny, nx = litter_2d.shape
            all_lx = domain_bounds[0] + (np.arange(nx) + 0.5) * voxel_size
            all_ly = domain_bounds[1] + (np.arange(ny) + 0.5) * voxel_size

            fx_min, fy_min, _, fx_max, fy_max, _ = forest_bounds[:6]
            mask_x = (all_lx >= fx_min - 1e-4) & (all_lx <= fx_max + 1e-4)
            mask_y = (all_ly >= fy_min - 1e-4) & (all_ly <= fy_max + 1e-4)

            col_idx = np.where(mask_x)[0]
            row_idx = np.where(mask_y)[0]

            if len(col_idx) > 0 and len(row_idx) > 0:
                c_min, c_max = col_idx[0], col_idx[-1]
                r_min, r_max = row_idx[0], row_idx[-1]
                cropped_litter = litter_2d[r_min : r_max + 1, c_min : c_max + 1]
                crop_lx = all_lx[c_min : c_max + 1]
                crop_ly = all_ly[r_min : r_max + 1]
            else:
                cropped_litter = litter_2d
                crop_lx = all_lx
                crop_ly = all_ly

            grid_x, grid_y = np.meshgrid(crop_lx, crop_ly)
            min_l = float(np.min(cropped_litter))
            max_l = float(np.max(cropped_litter))
            denom = max(1e-6, max_l - min_l)
            norm_lit = (cropped_litter - min_l) / denom
            ax.plot_surface(
                grid_x,
                grid_y,
                np.full_like(grid_x, domain_bounds[2]),
                facecolors=plt.cm.YlOrBr(norm_lit),
                rstride=1,
                cstride=1,
                shade=False,
                alpha=0.80,
                zorder=2,
            )

        # 3. Draw Unpadded Forest Plot & Outer Domain Bounding Boxes
        x_min, y_min, z_min, x_max, y_max, z_max = domain_bounds[:6]
        fx_min, fy_min, fz_min, fx_max, fy_max, fz_max = forest_bounds[:6]

        # Draw Outer Computational Domain Wireframe (Sky Mesh + Lateral Padding)
        dom_lines = [
            (
                [x_min, x_max, x_max, x_min, x_min],
                [y_min, y_min, y_max, y_max, y_min],
                [z_min, z_min, z_min, z_min, z_min],
            ),
            (
                [x_min, x_max, x_max, x_min, x_min],
                [y_min, y_min, y_max, y_max, y_min],
                [z_max, z_max, z_max, z_max, z_max],
            ),
            ([x_min, x_min], [y_min, y_min], [z_min, z_max]),
            ([x_max, x_max], [y_min, y_min], [z_min, z_max]),
            ([x_max, x_max], [y_max, y_max], [z_min, z_max]),
            ([x_min, x_min], [y_max, y_max], [z_min, z_max]),
        ]
        for idx, (lx, ly, lz) in enumerate(dom_lines):
            ax.plot(
                lx,
                ly,
                lz,
                color="#0077b6",
                linestyle=":",
                linewidth=1.0,
                alpha=0.6,
                label="FDS Domain & Sky Box" if idx == 0 else None,
            )

        # Draw Forest Plot Box (dark gray dashed lines)
        plot_corners = np.array(
            [
                [fx_min, fy_min, fz_min],
                [fx_max, fy_min, fz_min],
                [fx_max, fy_max, fz_min],
                [fx_min, fy_max, fz_min],
                [fx_min, fy_min, fz_min],
            ]
        )
        ax.plot(
            plot_corners[:, 0],
            plot_corners[:, 1],
            plot_corners[:, 2],
            "k--",
            linewidth=1.3,
            alpha=0.75,
            label="Forest Plot Footprint",
        )

        # 4. Render 2D Ignition Vent Polygon & Line
        vent_w = (
            float(wind_params.get("vent_width", 1.0))
            if isinstance(wind_params, dict)
            else 1.0
        )
        vent_pts, _ = compute_ignition_vent_polygon(
            ignition_boundary, forest_bounds, vent_width=vent_w
        )
        ign_pts, ign_label = compute_ignition_line_coords(
            ignition_boundary, forest_bounds, vent_width=vent_w
        )

        # Draw shaded ignition vent patch
        poly_verts = [vent_pts[:4]]
        poly_col = Poly3DCollection(
            poly_verts,
            facecolors="#e63946",
            alpha=0.35,
            edgecolors="#d90429",
            linewidths=1.5,
        )
        ax.add_collection3d(poly_col)

        # Draw bright ignition line
        ax.plot(
            ign_pts[:, 0],
            ign_pts[:, 1],
            ign_pts[:, 2],
            color="#e63946",
            linewidth=4.5,
            zorder=10,
            label=ign_label,
        )

        # 5. Render 3D Wind Vector Arrow (Cyan/Blue Arrow)
        arrow_start, arrow_dir, w_speed, wind_label = compute_wind_vector_arrow(
            wind_params, domain_bounds
        )
        if w_speed > 0.1:
            ax.quiver(
                arrow_start[0],
                arrow_start[1],
                arrow_start[2],
                arrow_dir[0],
                arrow_dir[1],
                arrow_dir[2],
                color="#0077b6",
                linewidth=3.0,
                arrow_length_ratio=0.35,
                label=wind_label,
            )

        # 6. Informational HUD Metadata Overlay Box
        plot_w = fx_max - fx_min
        plot_h = fy_max - fy_min
        plot_z = fz_max - fz_min
        dom_w = x_max - x_min
        dom_h = y_max - y_min
        dom_z = z_max - z_min
        max_bd = float(np.max(bulk_densities)) if len(bulk_densities) > 0 else 0.0
        mean_bd = float(np.mean(bulk_densities)) if len(bulk_densities) > 0 else 0.0
        total_mass = float(np.sum(bulk_densities) * (voxel_size**3))

        hud_text = (
            f"Preset: {preset_name}\n"
            f"Plot Extent: {plot_w:.1f} m × {plot_h:.1f} m × {plot_z:.1f} m\n"
            f"Domain Extent: {dom_w:.1f} m × {dom_h:.1f} m × {dom_z:.1f} m\n"
            f"Voxel Resolution: Δx = {voxel_size:.2f} m\n"
            f"{ign_label}\n"
            f"{wind_label}\n"
            f"Max Bulk Density: {max_bd:.2f} kg/m³\n"
            f"Mean Bulk Density: {mean_bd:.2f} kg/m³\n"
            f"Total Fuel Mass: {total_mass:.1f} kg"
        )
        bbox_props = dict(
            boxstyle="round,pad=0.6",
            facecolor="white",
            alpha=0.92,
            edgecolor="#0077b6",
            linewidth=1.2,
        )
        fig.text(
            0.02,
            0.96,
            hud_text,
            fontsize=9.0,
            verticalalignment="top",
            bbox=bbox_props,
            family="sans-serif",
        )

        ax.set_title(
            f"3D FDS Simulation Domain & Voxel Fuel Setup\n({preset_name})",
            fontsize=13,
            fontweight="bold",
            pad=15,
        )
        ax.set_xlabel("X Position (m)", fontsize=10, fontweight="bold")
        ax.set_ylabel("Y Position (m)", fontsize=10, fontweight="bold")
        ax.set_zlabel("Height Z (m)", fontsize=10, fontweight="bold")

        ax.legend(loc="upper right", fontsize=9.0)
        ax.view_init(elev=28, azim=-55)

        fig.tight_layout()
        fig.savefig(file_path, bbox_inches="tight")
        plt.close(fig)
    except Exception as e:
        print(f"[Scene Visualizer Warning] Matplotlib 3D render failed: {e}")


def export_3d_interactive_html(
    file_path: Path,
    voxel_coords: np.ndarray,
    bulk_densities: np.ndarray,
    domain_bounds: Union[tuple[float, ...], list[float]],
    forest_bounds: Union[tuple[float, ...], list[float]],
    voxel_size: float,
    ignition_boundary: Union[str, dict[str, Any]],
    wind_params: dict[str, Any],
    preset_name: str = "Custom Preset",
    litter_2d: Optional[np.ndarray] = None,
    litter_depth: float = 0.05,
) -> None:
    """Generates a standalone 3D interactive HTML model (.html) using Plotly."""
    try:
        import plotly.graph_objects as go

        # Sub-sample voxels if count > 45,000 for smooth web browser rendering
        max_pts = 45000
        if len(voxel_coords) > max_pts:
            idx = np.random.choice(len(voxel_coords), size=max_pts, replace=False)
            pts = voxel_coords[idx]
            bds = bulk_densities[idx]
        else:
            pts = voxel_coords
            bds = bulk_densities

        fig = go.Figure()

        # 1. 3D Volumetric Voxel Cubes (Mesh3d) matching actual simulation voxel size
        if len(pts) > 0:
            # 5% visual seam gap between adjacent voxels makes each individual voxel distinctly visible in 3D
            shrink_ratio = 0.95
            h = (voxel_size * shrink_ratio) / 2.0
            N = len(pts)
            unit_verts = np.array(
                [
                    [-h, -h, -h],
                    [h, -h, -h],
                    [h, h, -h],
                    [-h, h, -h],
                    [-h, -h, h],
                    [h, -h, h],
                    [h, h, h],
                    [-h, h, h],
                ],
                dtype=float,
            )
            all_verts = (pts[:, None, :] + unit_verts[None, :, :]).reshape(-1, 3)

            base_tri = np.array(
                [
                    [0, 1, 2],
                    [0, 2, 3],
                    [4, 6, 5],
                    [4, 7, 6],
                    [0, 5, 1],
                    [0, 4, 5],
                    [2, 7, 3],
                    [2, 6, 7],
                    [0, 3, 7],
                    [0, 7, 4],
                    [1, 5, 6],
                    [1, 6, 2],
                ],
                dtype=int,
            )
            triangles = (
                base_tri[None, :, :] + (np.arange(N) * 8)[:, None, None]
            ).reshape(-1, 3)
            face_intensity = np.repeat(bds, 12)

            hover_text = [
                f"<b>Fuel Voxel</b><br>"
                f"Center: ({c[0]:.2f}, {c[1]:.2f}, {c[2]:.2f}) m<br>"
                f"Voxel Size: {voxel_size:.2f} m<br>"
                f"Bulk Density: {b:.2f} kg/m³"
                for c, b in zip(pts, bds)
            ]
            face_hover = np.repeat(hover_text, 12)

            c_min = float(np.min(bds)) if len(bds) > 0 else 0.0
            c_max = float(np.max(bds)) if len(bds) > 0 else 1.0
            if c_min == c_max:
                c_min -= 0.1
                c_max += 0.1

            fig.add_trace(
                go.Mesh3d(
                    x=all_verts[:, 0],
                    y=all_verts[:, 1],
                    z=all_verts[:, 2],
                    i=triangles[:, 0],
                    j=triangles[:, 1],
                    k=triangles[:, 2],
                    intensity=face_intensity,
                    intensitymode="cell",
                    text=face_hover,
                    hoverinfo="text",
                    cmin=c_min,
                    cmax=c_max,
                    colorscale="YlOrRd",
                    colorbar=dict(
                        title=dict(
                            text="Fuel BD (kg/m³)",
                            font=dict(size=12, family="Arial", color="black"),
                        ),
                        thickness=18,
                        len=0.7,
                    ),
                    opacity=1.0,
                    flatshading=True,
                    lighting=dict(
                        ambient=0.88, diffuse=0.75, roughness=0.90, specular=0.04
                    ),
                    name=f"Fuel Voxel Cubes ({voxel_size:.2f}m)",
                )
            )

        # 1b. Add Flat 2D Ground Litter Layer (1D Boundary Fuel Model) strictly on the Forest Floor
        if litter_2d is not None and np.any(litter_2d > 0):
            ny, nx = litter_2d.shape
            all_lx = domain_bounds[0] + (np.arange(nx) + 0.5) * voxel_size
            all_ly = domain_bounds[1] + (np.arange(ny) + 0.5) * voxel_size

            fx_min, fy_min, _, fx_max, fy_max, _ = forest_bounds[:6]
            mask_x = (all_lx >= fx_min - 1e-4) & (all_lx <= fx_max + 1e-4)
            mask_y = (all_ly >= fy_min - 1e-4) & (all_ly <= fy_max + 1e-4)

            col_idx = np.where(mask_x)[0]
            row_idx = np.where(mask_y)[0]

            if len(col_idx) > 0 and len(row_idx) > 0:
                c_min, c_max = col_idx[0], col_idx[-1]
                r_min, r_max = row_idx[0], row_idx[-1]
                cropped_litter = litter_2d[r_min : r_max + 1, c_min : c_max + 1]
                crop_lx = all_lx[c_min : c_max + 1]
                crop_ly = all_ly[r_min : r_max + 1]
            else:
                cropped_litter = litter_2d
                crop_lx = all_lx
                crop_ly = all_ly

            c_ny, c_nx = cropped_litter.shape
            crop_fuel_load = cropped_litter * litter_depth

            lit_min = float(np.min(cropped_litter))
            lit_max = float(np.max(cropped_litter))
            if lit_min == lit_max:
                lit_min -= 0.1
                lit_max += 0.1

            fig.add_trace(
                go.Surface(
                    x=crop_lx,
                    y=crop_ly,
                    z=np.full((c_ny, c_nx), domain_bounds[2]),
                    surfacecolor=cropped_litter,
                    customdata=crop_fuel_load,
                    colorscale="YlOrBr",
                    cmin=lit_min,
                    cmax=lit_max,
                    opacity=0.90,
                    showscale=True,
                    colorbar=dict(
                        title=dict(
                            text="Litter BD (kg/m³)",
                            font=dict(size=11, family="Arial", color="black"),
                        ),
                        thickness=14,
                        len=0.55,
                        x=1.12,
                    ),
                    hovertemplate=(
                        "<b>Ground Litter (1D BFM)</b><br>"
                        "Position X: %{x:.2f} m<br>"
                        "Position Y: %{y:.2f} m<br>"
                        "Bulk Density: %{surfacecolor:.2f} kg/m³<br>"
                        "Fuel Load: %{customdata:.2f} kg/m²<br>"
                        f"Litter Depth: {litter_depth * 100.0:.1f} cm<extra></extra>"
                    ),
                    name="Ground Litter (1D BFM)",
                )
            )

        # 2. Add Forest Plot Footprint Box (Dark Gray Wireframe)
        fx_min, fy_min, fz_min, fx_max, fy_max, fz_max = forest_bounds[:6]
        x_corners = [
            fx_min,
            fx_max,
            fx_max,
            fx_min,
            fx_min,
            fx_min,
            fx_max,
            fx_max,
            fx_min,
            fx_min,
        ]
        y_corners = [
            fy_min,
            fy_min,
            fy_max,
            fy_max,
            fy_min,
            fy_min,
            fy_min,
            fy_max,
            fy_max,
            fy_min,
        ]
        z_corners = [
            fz_min,
            fz_min,
            fz_min,
            fz_min,
            fz_min,
            fz_max,
            fz_max,
            fz_max,
            fz_max,
            fz_max,
        ]

        fig.add_trace(
            go.Scatter3d(
                x=x_corners,
                y=y_corners,
                z=z_corners,
                mode="lines",
                line=dict(color="#4a4e69", width=4, dash="dash"),
                name="Forest Plot Footprint",
            )
        )

        # 3. Add Outer Computational Domain Box (Blue Wireframe)
        x_min, y_min, z_min, x_max, y_max, z_max = domain_bounds[:6]
        dom_x = [
            x_min,
            x_max,
            x_max,
            x_min,
            x_min,
            x_min,
            x_max,
            x_max,
            x_min,
            x_min,
            x_max,
            x_max,
            x_min,
            x_min,
        ]
        dom_y = [
            y_min,
            y_min,
            y_max,
            y_max,
            y_min,
            y_min,
            y_min,
            y_max,
            y_max,
            y_min,
            y_min,
            y_max,
            y_max,
            y_min,
        ]
        dom_z = [
            z_min,
            z_min,
            z_min,
            z_min,
            z_min,
            z_max,
            z_max,
            z_max,
            z_max,
            z_max,
            z_max,
            z_max,
            z_max,
            z_min,
        ]
        fig.add_trace(
            go.Scatter3d(
                x=dom_x,
                y=dom_y,
                z=dom_z,
                mode="lines",
                line=dict(color="#0077b6", width=2, dash="dot"),
                name="FDS Domain & Sky Box",
            )
        )

        # 4. Add 2D Ignition Vent Patch & Ignition Line
        vent_w = (
            float(wind_params.get("vent_width", 1.0))
            if isinstance(wind_params, dict)
            else 1.0
        )
        vent_pts, _ = compute_ignition_vent_polygon(
            ignition_boundary, forest_bounds, vent_width=vent_w
        )
        ign_pts, ign_label = compute_ignition_line_coords(
            ignition_boundary, forest_bounds, vent_width=vent_w
        )

        # Add vent patch outline
        fig.add_trace(
            go.Scatter3d(
                x=vent_pts[:, 0],
                y=vent_pts[:, 1],
                z=vent_pts[:, 2],
                mode="lines",
                line=dict(color="#d90429", width=4),
                name=f"{ign_label} (Vent Area)",
            )
        )

        # Add prominent ignition line
        fig.add_trace(
            go.Scatter3d(
                x=ign_pts[:, 0],
                y=ign_pts[:, 1],
                z=ign_pts[:, 2],
                mode="lines+markers",
                line=dict(color="#e63946", width=8),
                marker=dict(size=6, color="#e63946"),
                name=ign_label,
            )
        )

        # 5. Add Wind Direction Arrow Cone / Line (Cyan Arrow)
        arrow_start, arrow_dir, w_speed, wind_label = compute_wind_vector_arrow(
            wind_params, domain_bounds
        )
        if w_speed > 0.1:
            arrow_end = arrow_start + arrow_dir
            fig.add_trace(
                go.Scatter3d(
                    x=[arrow_start[0], arrow_end[0]],
                    y=[arrow_start[1], arrow_end[1]],
                    z=[arrow_start[2], arrow_end[2]],
                    mode="lines+markers",
                    line=dict(color="#0077b6", width=6),
                    marker=dict(size=[4, 9], color="#0077b6", symbol="diamond"),
                    name=wind_label,
                )
            )

        # 6. Configure Camera View Buttons & Interactive Layout
        updatemenus = [
            dict(
                type="buttons",
                direction="left",
                x=0.02,
                y=1.08,
                xanchor="left",
                yanchor="top",
                buttons=[
                    dict(
                        label="3D Perspective",
                        method="relayout",
                        args=[
                            {
                                "scene.camera": {
                                    "eye": {"x": 1.5, "y": -1.5, "z": 1.2},
                                    "up": {"x": 0, "y": 0, "z": 1},
                                }
                            }
                        ],
                    ),
                    dict(
                        label="Top View (XY)",
                        method="relayout",
                        args=[
                            {
                                "scene.camera": {
                                    "eye": {"x": 0.0, "y": 0.0, "z": 2.2},
                                    "up": {"x": 0, "y": 1, "z": 0},
                                }
                            }
                        ],
                    ),
                    dict(
                        label="Front View (XZ)",
                        method="relayout",
                        args=[
                            {
                                "scene.camera": {
                                    "eye": {"x": 0.0, "y": -2.2, "z": 0.0},
                                    "up": {"x": 0, "y": 0, "z": 1},
                                }
                            }
                        ],
                    ),
                    dict(
                        label="Side View (YZ)",
                        method="relayout",
                        args=[
                            {
                                "scene.camera": {
                                    "eye": {"x": 2.2, "y": 0.0, "z": 0.0},
                                    "up": {"x": 0, "y": 0, "z": 1},
                                }
                            }
                        ],
                    ),
                ],
            )
        ]

        fig.update_layout(
            title=dict(
                text=f"<b>Interactive 3D FDS Scene Preview</b><br>Preset: {preset_name}",
                x=0.02,
                y=0.96,
                font=dict(size=16, family="Arial"),
            ),
            updatemenus=updatemenus,
            scene=dict(
                xaxis=dict(title="X Position (m)", gridcolor="#e0e0e0"),
                yaxis=dict(title="Y Position (m)", gridcolor="#e0e0e0"),
                zaxis=dict(title="Height Z (m)", gridcolor="#e0e0e0"),
                aspectmode="data",
                camera=dict(eye=dict(x=1.5, y=-1.5, z=1.2)),
            ),
            margin=dict(l=10, r=10, b=10, t=70),
            paper_bgcolor="#ffffff",
            plot_bgcolor="#ffffff",
        )

        fig.write_html(str(file_path), include_plotlyjs="cdn")
    except ImportError:
        print(
            "[Scene Visualizer] Note: 'plotly' is not installed. Interactive 3D HTML scene preview skipped (install via: pip install plotly)."
        )
    except Exception as e:
        print(f"[Scene Visualizer Warning] Plotly HTML export failed: {e}")


def generate_scene_previews(
    voxel_coords: np.ndarray,
    bulk_densities: np.ndarray,
    domain_bounds: Union[tuple[float, ...], list[float]],
    forest_bounds: Union[tuple[float, ...], list[float]],
    voxel_size: float,
    ignition_boundary: Union[str, dict[str, Any]],
    wind_params: dict[str, Any],
    preset_name: str = "Custom Preset",
    output_dir: Union[str, Path] = ".",
    log_callback: Any = None,
    litter_2d: Optional[np.ndarray] = None,
    litter_depth: float = 0.05,
) -> dict[str, Path]:
    """Generates a standalone interactive 3D HTML scene preview file in output_dir."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    html_path = out_dir / "fds_scene_preview.html"

    # Export Standalone Interactive 3D HTML Model
    export_3d_interactive_html(
        html_path,
        voxel_coords,
        bulk_densities,
        domain_bounds,
        forest_bounds,
        voxel_size,
        ignition_boundary,
        wind_params,
        preset_name,
        litter_2d=litter_2d,
        litter_depth=litter_depth,
    )

    if log_callback:
        log_callback(
            f"Exported interactive 3D pre-simulation scene preview: {html_path.name}"
        )

    return {"html": html_path}
