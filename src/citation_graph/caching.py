from argparse import Namespace
from json import JSONEncoder, dump, load
from logging import getLogger
from pathlib import Path
from time import time
from typing import Any, Dict, List

from citation_graph.paper import AuthorName, Paper
from citation_graph.traverser import _PaperNode, Traverser
from citation_graph.utils import SLUG, get_cache_dir, get_valid_filename
from citation_graph.version import get_version


logger = getLogger(f"{SLUG}.caching")


class CustomJSONEncoder(JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, (Paper, AuthorName, _PaperNode)):
            d = o.__dict__
            d["__type"] = o.__class__.__name__
            return d
        elif isinstance(o, Traverser):
            return {
                "__type": "Traverser",
                "name": o.name,
                "papers": o.papers,
                "current_depth": o.current_depth + 1,
            }

        return super().default(o)


def create_objects(o: Any, traversers: List[Traverser]) -> Any:
    if isinstance(o, dict) and "__type" in o:
        if o["__type"] == "Paper":
            del o["__type"]
            return Paper(**o)
        elif o["__type"] == "AuthorName":
            del o["__type"]
            return AuthorName(**o)
        elif o["__type"] == "_PaperNode":
            del o["__type"]
            return _PaperNode(**o)
        elif o["__type"] == "Traverser":
            for traverser in traversers:
                if traverser.name == o["name"]:
                    traverser.papers = o["papers"]
                    traverser.current_depth = o["current_depth"]
                    return traverser

    return o


def get_cache_dir_for_paper(paper: Paper) -> Path:
    paper_id = paper.get_id() or "{:x}".format(id(paper))
    return get_cache_dir() / f"{get_valid_filename(paper_id)}.cache.json"


def is_cached(paper: Paper) -> bool:
    return get_cache_dir_for_paper(paper).exists()


def save_cache(paper: Paper, traversers: List[Traverser], args: Namespace) -> None:
    cache_dir = get_cache_dir()
    if not cache_dir.exists():
        cache_dir.mkdir(0o777, True, True)

    cache_file = get_cache_dir_for_paper(paper)

    meta = {
        "_meta": {
            "creator": SLUG,
            "version": get_version(),
            "time": time(),
            "start_paper": paper,
            "args": args.__dict__,
        }
    }
    data: Dict[str, Any] = {t.name: t for t in traversers}
    data.update(meta)

    with open(cache_file, "w") as f:
        dump(data, f, cls=CustomJSONEncoder)

        logger.info(f"Saved results to cache in {cache_file}")


def load_cached(paper: Paper, traversers: List[Traverser]) -> None:
    cache_file = get_cache_dir_for_paper(paper)

    logger.info(f"Restoring results from cached file {cache_file}")

    with open(cache_file, "r") as f:
        load(f, object_hook=lambda o: create_objects(o, traversers))
