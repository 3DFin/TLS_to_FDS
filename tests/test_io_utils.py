from tls_to_fds import io_utils
from tls_to_fds.models import OutputParams


def test_default_config_values():
    default_dev_time = io_utils.get_default("env_params", "wind_dev_time", 15.0)
    assert default_dev_time == 25.0


def test_safe_get():
    # Dataclass test
    out_params = OutputParams(
        hrrpua=True, flame=True, temp=True, wind=True, biomass=True, dt_restart=50.0
    )
    assert io_utils.safe_get(out_params, "dt_restart") == 50.0
    assert io_utils.safe_get(out_params, "non_existent", "default_val") == "default_val"

    # Dictionary test
    d = {"key1": "val1"}
    assert io_utils.safe_get(d, "key1") == "val1"
    assert io_utils.safe_get(d, "key2", 42) == 42


def test_load_preset():
    preset_data = io_utils.load_preset("ponderosa_pine_summer")
    assert "Canopy layer" in preset_data
    assert "Surface layer" in preset_data
    assert "Trunks" in preset_data
    assert "Litter" in preset_data
    assert "Ground Fuel" not in preset_data
    assert "Duff" not in preset_data
    assert "description" in preset_data


def test_get_preset_class_props():
    preset_data = io_utils.load_preset("ponderosa_pine_summer")
    canopy_props = io_utils.get_preset_class_props(preset_data, "Canopy layer")
    assert canopy_props is not None
    assert canopy_props.get("default_bulk_density") == 0.4

    # Alias matching
    alias_canopy = io_utils.get_preset_class_props(preset_data, "Canopy Fuel")
    assert alias_canopy == canopy_props

    surface_props = io_utils.get_preset_class_props(preset_data, "Surface layer")
    assert surface_props is not None
    assert surface_props.get("default_bulk_density") == 0.8

    alias_surface = io_utils.get_preset_class_props(preset_data, "Surface Fuel")
    assert alias_surface == surface_props

    trunk_props = io_utils.get_preset_class_props(preset_data, "Trunks")
    assert trunk_props is not None
    assert trunk_props.get("default_bulk_density") == 10.0

    litter_props = io_utils.get_preset_class_props(preset_data, "Litter")
    assert litter_props is not None
    assert litter_props.get("default_bulk_density") == 15.0

    # Non-existent layer
    assert io_utils.get_preset_class_props(preset_data, "Unknown Layer") is None


def test_load_preset_invalid():
    import pytest

    with pytest.raises(ValueError):
        io_utils.load_preset("")

    with pytest.raises(FileNotFoundError):
        io_utils.load_preset("non_existent_preset_xyz_123")


def test_generate_fortran_validation(tmp_path):
    import numpy as np
    import pytest

    pts = np.array([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]])

    with pytest.raises(ValueError):
        io_utils.generate_fortran(
            "test", pts, voxel_size=-0.25, bd=1.0, output_dir=tmp_path
        )

    with pytest.raises(FileNotFoundError):
        io_utils.generate_fortran(
            "test", pts, voxel_size=0.25, bd=1.0, output_dir=tmp_path / "missing_dir"
        )


def test_get_presets_dir_source():
    p = io_utils.get_presets_dir()
    assert p.exists()
    assert any(p.glob("*.json"))


def test_get_presets_dir_macos_bundle(monkeypatch, tmp_path):
    import sys

    # Simulate frozen macOS app bundle:
    # TLS_to_FDS.app/Contents/MacOS/TLS_to_FDS
    # TLS_to_FDS.app/Contents/Resources/presets/sample.json
    bundle_macos = tmp_path / "TLS_to_FDS.app" / "Contents" / "MacOS"
    bundle_macos.mkdir(parents=True)
    fake_exe = bundle_macos / "TLS_to_FDS"
    fake_exe.touch()

    bundle_resources_presets = (
        tmp_path / "TLS_to_FDS.app" / "Contents" / "Resources" / "presets"
    )
    bundle_resources_presets.mkdir(parents=True)
    (bundle_resources_presets / "sample.json").write_text("{}")

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    if hasattr(sys, "_MEIPASS"):
        monkeypatch.delattr(sys, "_MEIPASS")

    found_dir = io_utils.get_presets_dir()
    assert found_dir == bundle_resources_presets
