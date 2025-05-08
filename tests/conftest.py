import pytest
import os
import shutil
from chord_striker.hit_maker import create_song, create_album


@pytest.fixture
def test_output_dir(tmp_path):
    """Create a temporary directory for test outputs."""
    output_dir = tmp_path / "test_output"
    output_dir.mkdir()
    yield str(output_dir)
    # Cleanup after test
    shutil.rmtree(output_dir)


@pytest.fixture
def test_seed():
    """Provide a fixed seed for reproducible tests."""
    return 42


@pytest.fixture
def test_key():
    """Provide a test key."""
    return "C"


@pytest.fixture
def test_tempo():
    """Provide a test tempo."""
    return 120
