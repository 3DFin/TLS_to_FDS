import pytest

def test_imports():
    """Basic test to ensure modules can be imported without syntax errors."""
    import tls_to_fds
    from tls_to_fds import models
    from tls_to_fds import io_utils
    from tls_to_fds import spatial_utils
    from tls_to_fds import fds_builder
    
    assert True
