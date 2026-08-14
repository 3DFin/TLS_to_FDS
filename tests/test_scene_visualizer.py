import numpy as np

from tls_to_fds import scene_visualizer


def test_compute_ignition_line_coords():
    forest_bounds = (0.0, 0.0, 0.0, 20.0, 20.0, 10.0)

    # Test South Edge (GUI string format)
    pts_s, label_s = scene_visualizer.compute_ignition_line_coords(
        "Line: South Edge (y_min)", forest_bounds
    )
    assert label_s == "Ignition: South Edge"
    assert pts_s.shape == (2, 3)
    assert pts_s[0, 1] == 0.0
    assert pts_s[1, 1] == 0.0

    # Test North Edge (GUI string format)
    pts_n, label_n = scene_visualizer.compute_ignition_line_coords(
        "Line: North Edge (y_max)", forest_bounds
    )
    assert label_n == "Ignition: North Edge"
    assert pts_n[0, 1] == 20.0
    assert pts_n[1, 1] == 20.0

    # Test East Edge (GUI string format)
    pts_e, label_e = scene_visualizer.compute_ignition_line_coords(
        "Line: East Edge (x_max)", forest_bounds
    )
    assert label_e == "Ignition: East Edge"
    assert pts_e[0, 0] == 20.0
    assert pts_e[1, 0] == 20.0

    # Test West Edge (GUI string format)
    pts_w, label_w = scene_visualizer.compute_ignition_line_coords(
        "Line: West Edge (x_min)", forest_bounds
    )
    assert label_w == "Ignition: West Edge"
    assert pts_w[0, 0] == 0.0
    assert pts_w[1, 0] == 0.0

    # Test Corner Points (GUI string format)
    pts_ne, label_ne = scene_visualizer.compute_ignition_line_coords(
        "Point: North-East Corner", forest_bounds
    )
    assert label_ne == "Ignition: NE Corner"

    pts_se, label_se = scene_visualizer.compute_ignition_line_coords(
        "Point: South-East Corner", forest_bounds
    )
    assert label_se == "Ignition: SE Corner"

    pts_sw, label_sw = scene_visualizer.compute_ignition_line_coords(
        "Point: South-West Corner", forest_bounds
    )
    assert label_sw == "Ignition: SW Corner"

    pts_nw, label_nw = scene_visualizer.compute_ignition_line_coords(
        "Point: North-West Corner", forest_bounds
    )
    assert label_nw == "Ignition: NW Corner"

    # Test Dict input
    pts_sw_dict, label_sw_dict = scene_visualizer.compute_ignition_line_coords(
        {"type": "Corner", "location": "SW"}, forest_bounds
    )
    assert "SW" in label_sw_dict
    assert len(pts_sw_dict) == 3

    # Test Vent Polygon
    poly, poly_label = scene_visualizer.compute_ignition_vent_polygon(
        "Line: South Edge (y_min)", forest_bounds, vent_width=2.0
    )
    assert poly.shape == (5, 3)
    assert poly[0, 1] == 0.0
    assert poly[2, 1] == 2.0


def test_compute_wind_vector_arrow():
    domain_bounds = (0.0, 0.0, 0.0, 50.0, 50.0, 30.0)
    wind_params = {"wind_speed": 6.5, "wind_direction": 270.0}

    start, direction, speed, label = scene_visualizer.compute_wind_vector_arrow(
        wind_params, domain_bounds
    )
    assert speed == 6.5
    assert "6.5 m/s" in label
    assert len(start) == 3
    assert len(direction) == 3


def test_generate_scene_previews(tmp_path):
    voxel_coords = np.array(
        [[2.0, 2.0, 1.0], [4.0, 4.0, 2.0], [6.0, 6.0, 3.0], [8.0, 8.0, 4.0]]
    )
    bulk_densities = np.array([1.5, 3.0, 4.5, 6.0])
    domain_bounds = (0.0, 0.0, 0.0, 20.0, 20.0, 10.0)
    forest_bounds = (1.0, 1.0, 0.0, 19.0, 19.0, 10.0)
    voxel_size = 1.0
    ignition_boundary = "South"
    wind_params = {"wind_speed": 5.0, "wind_direction": 270.0}
    preset_name = "Test Biome Preset"

    litter_2d = np.array([[10.0, 15.0], [12.0, 18.0]])

    result = scene_visualizer.generate_scene_previews(
        voxel_coords=voxel_coords,
        bulk_densities=bulk_densities,
        domain_bounds=domain_bounds,
        forest_bounds=forest_bounds,
        voxel_size=voxel_size,
        ignition_boundary=ignition_boundary,
        wind_params=wind_params,
        preset_name=preset_name,
        output_dir=tmp_path,
        litter_2d=litter_2d,
    )

    assert "html" in result
    assert result["html"].exists()
    assert result["html"].stat().st_size > 0
