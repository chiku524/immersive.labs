"""Immersive Labs Video Game Generation Studio worker."""

from importlib.metadata import PackageNotFoundError, version


def _read_version() -> str:
    try:
        return version("immersive-studio")
    except PackageNotFoundError:
        return "0.0.0"


__version__ = _read_version()
