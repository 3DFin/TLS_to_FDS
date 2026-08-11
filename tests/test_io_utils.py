import pytest
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
    assert "Surface Fuel" in preset_data or "Litter" in preset_data
    assert "description" in preset_data
