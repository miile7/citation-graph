from argparse import Namespace
from contextlib import AbstractContextManager
from copy import deepcopy
from io import TextIOWrapper
from json import JSONEncoder, dump, load
from logging import Logger, getLogger
from pathlib import Path
from queue import SimpleQueue
from threading import Thread
from time import time
from typing import Any, Dict, List, Literal, Optional
from citation_graph.database import Database

from citation_graph.paper import AuthorName, Paper
from citation_graph.utils import SLUG, get_cache_dir, get_valid_filename
from citation_graph.version import get_version


FILE_SPECIFICATION_VERSION = 2


class CustomJsonEncoder(JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, (Paper, AuthorName)):
            d = o.__dict__
            d["__type"] = o.__class__.__name__
            return d
        elif isinstance(o, Path):
            return {"__type": "Path", "path": str(o)}

        return super().default(o)


class _StopMessage:
    pass


class CacheWorker(Thread):
    running: bool
    queue: SimpleQueue
    logger: Logger
    cache_file_path: Path

    def __init__(self, queue: SimpleQueue, cache_file_path: Path) -> None:
        super().__init__(name="citation_graph.cache_manager.CacheWorker")

        self.queue = queue
        self.cache_file_path = cache_file_path

        self.logger = getLogger("citation_graph.cache_manager.CacheWorker")
        self.running = False

    def start(self) -> None:
        self.running = True
        self.logger.debug("Starting cache manager working thread")
        return super().start()

    def stop(self) -> None:
        self.logger.debug("Stopping cache manager working thread")
        self.running = False

    def run(self) -> None:
        while self.running:
            data = self.queue.get()
            if isinstance(data, _StopMessage):
                self.logger.debug("Received stop message")
                self.stop()
                return

            with open(self.cache_file_path, "w", encoding="utf-8") as cache_file:
                self.logger.debug("Saving data")
                dump(data, cache_file, cls=CustomJsonEncoder)


class CacheManager(AbstractContextManager):
    start_paper: Paper
    databases: List[Database]
    args: Namespace
    load_cache: bool

    cache_file_path: Path
    logger: Logger

    data: Dict[str, Any]
    queue: SimpleQueue

    def __init__(
        self,
        start_paper: Paper,
        databases: List[Database],
        args: Namespace,
        load_cache_on_startup: bool,
        cache_path: Optional[Path] = None,
    ) -> None:
        cache_dir: Path
        if isinstance(cache_path, Path):
            if cache_path.is_dir():
                cache_dir = cache_path
                self.cache_file_path = cache_path / self.get_cache_file_name(
                    self.start_paper
                )
            else:
                cache_dir = cache_path.parent
                self.cache_file_path = cache_path
        else:
            cache_dir = get_cache_dir()
            self.cache_file_path = get_cache_dir() / self.get_cache_file_name(
                self.start_paper
            )

        if not cache_dir.exists():
            cache_dir.mkdir(0o777, True, True)

        self.start_paper = start_paper
        self.databases = databases
        self.args = args
        self.logger = getLogger("citation_graph.cache_manager.CacheManager")

        self.load_cache = load_cache_on_startup
        self.data = {}
        self.queue = SimpleQueue()
        self.worker = CacheWorker(self.queue, self.cache_file_path)

    def __enter__(self) -> "CacheManager":
        self.logger.info(f"Initializing cache file {self.cache_file_path}")

        self._read_cache_file_if_exists()

        if not isinstance(self.data, dict):
            self.data = {}

        if "_meta" not in self.data:
            self.data["_meta"] = []

        self.data["_meta"].append(
            {
                "creator": SLUG,
                "file-spec-version": FILE_SPECIFICATION_VERSION,
                "version": get_version(),
                "time": time(),
                "start_paper": self.start_paper,
                "args": self.args.__dict__,
            }
        )

        self.worker.start()

        self.save()

        return self

    def __exit__(self, exc_type, exc_value, traceback) -> Literal[False]:
        self.queue.put(_StopMessage())
        self.worker.stop()
        return False  # return False to not suppress any exceptions

    def get_cache_file_name(self, paper: Paper) -> str:
        paper_id = str(paper.get_raw_id()) or "{:x}".format(id(paper))
        return f"{get_valid_filename(paper_id)}.cache.json"

    def has_cache_file(self) -> bool:
        if not self.cache_file_path.exists():
            return False

        stat = self.cache_file_path.stat()
        return stat.st_size > 0

    def save(self, database: Optional[Database] = None) -> None:
        if isinstance(database, Database):
            self.data[database.name] = database.toJson()
            self.logger.debug(
                f"Updating cache for database {database.name} in cache manager local "
                "data"
            )
        else:
            self.data.update({db.name: db.toJson() for db in self.databases})
            self.logger.debug(
                "Updating all database caches in cache manager local data"
            )

        data = deepcopy(self.data)

        self.logger.debug("Queuing save data")
        self.queue.put(data)

    def _read_cache_file_if_exists(self) -> None:
        if not self.has_cache_file():
            self.logger.debug("No cache file found")
            return

        if not self.load_cache:
            self.logger.info(
                f"Ignoring cache file {self.cache_file_path}, cache is disabled, "
                "probably by --clear-cache."
            )
            return

        with open(self.cache_file_path, "r", encoding="utf-8") as cache_file:
            load(cache_file, object_hook=self._read_file_create_objects)

    def _read_file_create_objects(self, o: Any) -> Any:
        if isinstance(o, dict) and "__type" in o:
            if o["__type"] == "Paper":
                del o["__type"]
                return Paper(**o)
            elif o["__type"] == "AuthorName":
                del o["__type"]
                return AuthorName(**o)
            elif o["__type"] == "Path":
                return Path(o["path"])
            elif o["__type"] == "Database":
                for database in self.databases:
                    if database.name == o["name"]:
                        database.citation_cache = o["citation_cache"]
                        database.paper_cache = o["paper_cache"]

                        self.logger.info(
                            f"Restored {len(database.paper_cache)} papers and"
                            f" {len(database.citation_cache)} citation connections "
                            f"from cache for database {database.name}"
                        )
                        break

        return o
