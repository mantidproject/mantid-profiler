from importlib.metadata import version, PackageNotFoundError
try:
    __version__ = version("mantidprofiler")
except PackageNotFoundError:
    __version__ = "0+local"
