from os import path


def get_version() -> str:
    with open(path.join(path.dirname(__file__), "VERSION"), "r") as f:
        for line in f:
            return line
    raise IOError("Cannot find VERSION file.")


__version__ = get_version()
