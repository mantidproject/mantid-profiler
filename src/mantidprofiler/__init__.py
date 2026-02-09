from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mantidprofiler")
except PackageNotFoundError:
    __version__ = "0+local"
