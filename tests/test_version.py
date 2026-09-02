"""Public package version stays aligned with installed metadata."""

from importlib.metadata import version

import aparta


def test_public_version_matches_distribution_metadata():
    assert aparta.__version__ == version("aparta")
