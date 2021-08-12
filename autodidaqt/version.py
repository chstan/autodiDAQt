import sys

if sys.version_info >= (3, 8):
    from importlib import metadata as importlib_metadata
else:
    import importlib_metadata


def get_version() -> str:
    try:
        return importlib_metadata.version(__name__.split(".version")[0])
    except importlib_metadata.PackageNotFoundError:
        return "unknown"


version: str = get_version()
VERSION: str = version
__version__: str = version
