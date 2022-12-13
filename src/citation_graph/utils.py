from colorsys import hsv_to_rgb
from os import name, environ, path
from pathlib import Path
from re import compile
from sys import platform
from typing import Iterable, Tuple

SLUG = "citation_graph"


NON_FILENAME_CHARS = compile(r"[^\w\d _\-,\.+()]+")


def get_cache_dir() -> Path:
    # Linux, Unix, AIX, etc.
    if name == "posix" and platform != "darwin":
        # use ~/.cache if empty OR not set
        xdg = environ.get("XDG_CACHE_HOME", None) or path.expanduser("~/.cache")
        return Path(xdg, SLUG)
    elif platform == "darwin":
        return Path(path.expanduser("~"), f"Library/Caches/{SLUG}")
    else:
        # Windows
        local = environ.get("LOCALAPPDATA", None) or path.expanduser(
            "~\\AppData\\Local"
        )
        return Path(local, SLUG)


def get_valid_filename(name: str) -> str:
    return NON_FILENAME_CHARS.sub("-", name)


def min_max(iter: Iterable[float]) -> Tuple[float, float]:
    min = float("INF")
    max = -float("INF")

    for i in iter:
        if i < min:
            min = i
        if i > max:
            max = i
    return min, max


def hsv_to_hex(h: float, s: float, v: float) -> str:
    r, g, b = hsv_to_rgb(h, s, v)

    return "#{:02X}{:02X}{:02X}".format(int(r * 255), int(g * 255), int(b * 255))
