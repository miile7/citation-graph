from colorsys import hsv_to_rgb
from math import log10
from os import name, environ, path
from pathlib import Path
from re import compile
from sys import platform
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, TypeVar

from citation_graph.paper import Paper

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


def get_hsv(
    value: Optional[float],
    value_range: Tuple[float, float],
    color_range: Tuple[float, float] = (0.6, 1),
) -> Tuple[float, float, float]:
    if value is None:
        return (0, 0, 0.5)

    return (
        (value - value_range[0])
        / (value_range[1] - value_range[0])
        * (color_range[1] - color_range[0])
        + color_range[0],
        1,
        1,
    )


def get_size(paper: Paper) -> float:
    return 10 * log10(
        # return (
        paper.citation_count + 2
        if isinstance(paper.citation_count, int)
        else 2
    )


def hsv_to_hex(h: float, s: float, v: float) -> str:
    r, g, b = hsv_to_rgb(h, s, v)

    return "#{:02X}{:02X}{:02X}".format(int(r * 255), int(g * 255), int(b * 255))


T = TypeVar("T")


def get_colormap(values: List[T]) -> Dict[T, str]:
    color_map: Dict[T, str] = {}
    m = len(values)

    for i, value in enumerate(
        sorted(values, key=lambda v: v if isinstance(v, (int, float)) else -1)
    ):
        color_map[value] = hsv_to_hex(*get_hsv(i, (0, m)))

    return color_map


def create_html_table(table: Iterable[Sequence[Any]]) -> str:
    column_number = max((len(c) for c in table))

    html_table = ["<table>"]
    for row in table:
        html_table.append("<tr>")

        html_table += [f"<td>{c}</td>" for c in row]
        html_table += ["<td></td>"] * (column_number - len(row))

        html_table.append("</tr>")

    html_table.append("</table>")
    return "".join(html_table)
