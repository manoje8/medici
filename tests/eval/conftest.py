"""
Eval-specific pytest configuration.

Provides the ``eval`` marker so evaluation tests can be run independently::

    pytest tests/eval/ -m eval -v

or excluded from normal test runs::

    pytest tests/ -m "not eval"
"""

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "eval: marks tests as evaluation tests (requires live LLM and Qdrant)",
    )


@pytest.fixture
def golden_set_path():
    """Return the path to the golden evaluation set."""
    from pathlib import Path

    path = Path(__file__).resolve().parent / "golden_set.json"
    if not path.exists():
        pytest.skip(f"Golden set not found: {path}")
    return path
