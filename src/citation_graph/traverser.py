from asyncio import sleep
from dataclasses import dataclass
from logging import DEBUG, getLogger
from networkx import Graph as NXGraph  # type: ignore[import]
from random import random
from typing import (
    Any,
    Callable,
    Coroutine,
    Dict,
    Generator,
    Generic,
    List,
    Optional,
    Tuple,
    TypeVar,
)
from citation_graph.database import Database

from citation_graph.paper import Paper
from citation_graph.utils import get_colormap, get_size, create_html_table


@dataclass
class _PaperNode:
    depth: int
    paper: Paper
    parent_id: Optional[str]


_T = TypeVar("_T")


@dataclass
class _GraphNode(Generic[_T]):
    node: _T
    children: List["_GraphNode[_T]"]


Graph = _GraphNode


class Traverser:
    start_paper: Paper
    save_callback: Callable[["Database"], Any]
    max_citations_per_paper: int
    error_count_threshold: int
    politeness_factor: float
    databases: List[Database]

    max_depth: int
    papers: Dict[str, _PaperNode]
    current_depth: int
    _error_count: int
    exclude_papers: List[Paper]

    def __init__(
        self,
        start_paper: Paper,
        save_callback: Callable[["Database"], Any],
        databases: List[Database],
        max_citations_per_paper: int = 300,
        politeness_factor: float = 1,
        error_count_threshold: int = 10,
        exclude_papers: List[Paper] = [],
    ) -> None:
        self.logger = getLogger("citation_graph.traverser.Traverser")
        self.logger.debug("Initialize traverser object")

        self.databases = databases
        self.start_paper = start_paper

        self.save_callback = save_callback
        self.max_citations_per_paper = max_citations_per_paper
        self.politeness_factor = politeness_factor
        self.error_count_threshold = error_count_threshold
        self.exclude_papers = exclude_papers

        self.reset()

    def reset(self) -> None:
        self.papers = {}
        self._add_paper_node(0, self.start_paper, None)

    def _add_paper_node(
        self, level: int, paper: Paper, parent_id: Optional[str]
    ) -> None:
        id = paper.get_id()
        if id is not None:
            self.papers[id] = _PaperNode(level, paper, parent_id)

    def _iter_papers_for_level(self, level: int) -> Generator[Paper, None, None]:
        for node in self.papers.values():
            if node.depth == level:
                yield node.paper

    def _register_cited_by(self, level: int, paper: Paper, parent: Paper) -> bool:
        if paper.get_id() in self.papers:
            self.logger.debug(
                f"Skipping registration of {paper} citing {parent}, {paper} is already "
                "included in result set"
            )
            return False

        self.logger.debug(f"Registering {paper} to cite {parent}")
        self._add_paper_node(level, paper, parent.get_id())
        return True

    def _add_citation_count(
        self, paper_id: Optional[str], citation_count_inc: int
    ) -> None:
        if paper_id in self.papers:
            node = self.papers[paper_id]
            if node.paper.citation_count is None:
                node.paper.citation_count = 0
            node.paper.citation_count += citation_count_inc

    async def _collect_papers_for_next_level(self, current_level: int) -> None:
        tasks: List[Coroutine[Any, Any, Tuple[Paper, List[Paper]]]] = []
        for parent in list(self._iter_papers_for_level(current_level)):
            self.logger.debug(f"Finding citations of {parent}")
            tasks.append(self._get_parent_and_cited_by(parent))

        for task in tasks:
            parent, cited_by_papers = await task
            self.logger.debug(f"Found {len(cited_by_papers)} citations of {parent}")
            for paper in cited_by_papers:
                self._register_cited_by(current_level + 1, paper, parent)

            self._add_citation_count(parent.get_id(), len(cited_by_papers))

    async def collect(self, max_depth: int) -> None:
        self.current_depth = 0

        self.logger.debug(
            f"Collecting citations until depth of {max_depth} for paper "
            f"{self.start_paper}."
        )

        self.max_depth = max_depth
        self._error_count = 0

        for self.current_depth in range(0, self.max_depth):
            self.logger.info(f"Loading level {self.current_depth}")
            await self._collect_papers_for_next_level(self.current_depth)

    async def _get_parent_and_cited_by(
        self, parent: Paper
    ) -> Tuple[Paper, List[Paper]]:
        cited_by: List[Paper] = []
        tasks: List[Coroutine[Any, Any, List[Paper]]] = []

        for database in self.databases:
            tasks.append(self._get_cited_by_from_database(parent, database))

        for task in tasks:
            cited_by += filter(
                lambda t: t not in cited_by and t not in self.exclude_papers, await task
            )

        return parent, cited_by

    async def _get_cited_by_from_database(
        self, parent: Paper, database: Database
    ) -> List[Paper]:
        cited_by: List[Paper] = []
        perform_next_request = True
        for offset in range(0, self.max_citations_per_paper, database.page_size):
            if not perform_next_request:
                self.logger.info(
                    f"Skipping remaining requests for {parent}, no more citations exist"
                )
                break

            if self._error_count > self.error_count_threshold:
                self.logger.warning(
                    f"Stopping requests for {parent}, reached {self._error_count} "
                    "errors over the last cycles. Eventually the request limit of the "
                    "database is reached."
                )
                return cited_by

            limit = (
                self.max_citations_per_paper - offset
                if self.max_citations_per_paper < offset + database.page_size
                else database.page_size
            )

            idle_time = database.idle_time * self.politeness_factor * random()

            if idle_time > 0 and database.wait_before_request(parent, offset, limit):
                self.logger.info(
                    f"Waiting random time {idle_time}s for polite api access before "
                    f"request for {parent}"
                )
                await sleep(idle_time)
            elif self.logger.level <= DEBUG:
                msgs = []
                if idle_time == 0:
                    msgs.append("idle time is zero")
                if not database.wait_before_request(parent, offset, limit):
                    msgs.append(f"database '{database.name}' signals not to wait")

                self.logger.debug(f"Skipping waiting time, {' and '.join(msgs)}")

            try:
                from_cache_only = database.has_all_citation_cache_entries(
                    parent, offset, limit
                )
                new_cited_by = await database.get_cited_by(parent, offset, limit)
                self._error_count = 0
                perform_next_request = len(new_cited_by) >= limit

                cited_by += new_cited_by

                if not from_cache_only:
                    self.save_callback(database)
            except Exception as e:
                self.logger.exception(e)
                self._error_count += 1

        return cited_by

    @staticmethod
    def to_list(traverser: "Traverser") -> List[Paper]:
        if len(traverser.papers) <= 1:
            raise Exception("Run Traverser.collect() before parsing to a list.")

        return [
            node.paper
            for node in sorted(traverser.papers.values(), key=lambda node: node.depth)
        ]

    @staticmethod
    def to_graph(traverser: "Traverser") -> Graph[Paper]:
        if len(traverser.papers) <= 1:
            raise Exception("Run Traverser.collect() before parsing to a list.")

        root: Optional[Paper] = None
        for node in traverser.papers.values():
            if node.depth == 0:
                root = node.paper
                break

        if root is None:
            raise Exception("Could not find root paper.")

        return Traverser._recursive_create_graph_nodes(traverser, root)

    @staticmethod
    def _recursive_create_graph_nodes(
        traverser: "Traverser", parent: Paper
    ) -> _GraphNode[Paper]:
        children: List[_GraphNode[Paper]] = []

        for node in traverser.papers.values():
            if node.parent_id == parent.get_id():
                children.append(
                    Traverser._recursive_create_graph_nodes(traverser, node.paper)
                )

        return _GraphNode(parent, children)

    @staticmethod
    def to_nx_graph(traverser: "Traverser") -> NXGraph:
        if len(traverser.papers) <= 1:
            raise Exception("Run Traverser.collect() before parsing to a list.")

        root: Optional[Paper] = None
        for node in traverser.papers.values():
            if node.depth == 0:
                root = node.paper
                break

        if root is None:
            raise Exception("Could not find root paper.")

        graph = NXGraph()

        color_map = get_colormap([n.paper.year for n in traverser.papers.values()])

        Traverser._add_nx_graph_node(graph, root, color_map)
        Traverser._recursive_create_nx_graph_nodes(traverser, root, graph, color_map)

        return graph

    @staticmethod
    def _add_nx_graph_node(
        graph: NXGraph, paper: Paper, color_map: Dict[int, str]
    ) -> None:
        graph.add_node(
            paper.get_id(),
            label=str(paper),
            size=get_size(paper),
            color=color_map[paper.year],
            # group=paper.year,
            year=paper.year,
            has_citations=paper.citation_count is not None and paper.citation_count > 0,
            has_expected_citations=(
                len(paper.expected_citation_count) is not None
                and any(paper.expected_citation_count.values())
            ),
            title=(
                f"<h3>{paper.title}</h3>"
                f"<p>{paper.year}, {paper.get_authors_str()}</p>"
                # f"<p>{paper.abstract}</p>"
            )
            + create_html_table(
                (
                    ("Url", f"<a target='_blank' href='{paper.url}'>{paper.url}</a>"),
                    ("Id", f"<code>{paper.get_id()}</code>"),
                    (
                        "Actual citation count",
                        paper.citation_count
                        if paper.citation_count is not None
                        else "?",
                    ),
                    (
                        "Expected citation count",
                        ", ".join(
                            f"{n}: {v}"
                            for n, v in paper.expected_citation_count.items()
                        )
                        if len(paper.expected_citation_count) > 0
                        else "?",
                    ),
                    ("Meta", f"<pre>{paper.meta}</pre>"),
                )
            ),
        )

    @staticmethod
    def _add_nx_graph_edge(graph: NXGraph, parent: Paper, paper: Paper) -> None:
        graph.add_edge(parent.get_id(), paper.get_id())

    @staticmethod
    def _recursive_create_nx_graph_nodes(
        traverser: "Traverser",
        parent: Paper,
        graph: NXGraph,
        color_map: Dict[int, str],
    ) -> None:
        for node in traverser.papers.values():
            if node.parent_id == parent.get_id():
                Traverser._add_nx_graph_node(graph, node.paper, color_map)
                Traverser._add_nx_graph_edge(graph, parent, node.paper)

                Traverser._recursive_create_nx_graph_nodes(
                    traverser, node.paper, graph, color_map
                )
