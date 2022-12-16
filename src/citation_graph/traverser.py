from asyncio import sleep
from dataclasses import dataclass
from logging import getLogger
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
    Union,
)

from citation_graph.paper import IdType, Paper
from citation_graph.utils import get_hsv, get_size, hsv_to_hex, min_max


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
    name: str
    save_callback: Callable[[], Any]
    page_size: int
    max_citations_per_paper: int
    use_pagination: bool
    idle_time: float  # idle time between two requests in s
    error_count_threshold: int

    max_depth: int
    start_paper: Paper
    papers: Dict[str, _PaperNode]
    current_depth: int
    _error_count: int

    def __init__(
        self,
        save_callback: Callable[[], Any],
        page_size: int = 100,
        max_citations_per_paper: int = 300,
        politeness_factor: float = 1,
        idle_time: float = 0.5,
        error_count_threshold: int = 10,
    ) -> None:
        self.logger = getLogger("citation_graph.traverser.Traverser")
        self.logger.debug("Initialize traverser object")

        self.papers = {}

        self.save_callback = save_callback
        self.page_size = page_size
        self.max_citations_per_paper = max_citations_per_paper
        self.use_pagination = True
        self.idle_time = idle_time * politeness_factor
        self.error_count_threshold = error_count_threshold

    def __str__(self) -> str:
        return f"Traverser{{{self.name}}}"

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

    async def collect(self, start_paper: Paper, max_depth: int) -> None:
        await self.resume_collection(start_paper, max_depth)

    async def resume_collection(self, start_paper: Paper, max_depth: int) -> None:
        if len(self.papers) == 0 or self.current_depth == 0:
            self.current_depth = 0
            self.papers = {}
            self._add_paper_node(0, start_paper, None)

            self.logger.debug(
                f"Collecting citations until depth of {max_depth} for paper "
                f"{start_paper}."
            )
        else:
            self.logger.debug(
                f"Resuming collecting citations from depth {self.current_depth} until "
                f"depth of {max_depth} for paper {start_paper}."
            )

        self.max_depth = max_depth
        self.start_paper = start_paper
        self._error_count = 0

        for self.current_depth in range(self.current_depth, self.max_depth):
            self.logger.debug(f"Performing step {self.current_depth}")
            await self._collect_papers_for_next_level(self.current_depth)

            self.save_callback()

    async def _get_parent_and_cited_by(
        self, parent: Paper
    ) -> Tuple[Paper, List[Paper]]:
        cited_by: List[Paper] = []

        for offset in range(0, self.max_citations_per_paper, self.page_size):
            if self._error_count > self.error_count_threshold:
                # probably too many requests
                return parent, cited_by

            if self.idle_time > 0 and self._wait_before_request(parent):
                self.logger.info(
                    f"Waiting random time [0..{self.idle_time})s for polite api "
                    f"access before request for {parent}"
                )
                await sleep(self.idle_time * random())

            try:
                limit = (
                    self.max_citations_per_paper - offset
                    if self.max_citations_per_paper < offset + self.page_size
                    else self.page_size
                )
                new_cited_by = await self._get_cited_by(parent, offset, limit)
                self._error_count = 0

                if len(new_cited_by) == 0:
                    break
                else:
                    cited_by += new_cited_by
            except Exception:
                self._error_count += 1

        return parent, cited_by

    def _wait_before_request(self, paper: Paper) -> bool:
        return True

    async def _get_cited_by(self, paper: Paper, offset: int, limit: int) -> List[Paper]:
        """Get all papers that cite the `paper` from the parameters."""
        raise NotImplementedError()

    async def get_paper(self, id_type: IdType, id: Union[str, int]) -> Paper:
        raise NotImplementedError()

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

        year_range = min_max((n.paper.year for n in traverser.papers.values()))

        Traverser._add_nx_graph_node(graph, root, year_range)
        Traverser._recursive_create_nx_graph_nodes(traverser, root, graph, year_range)

        return graph

    @staticmethod
    def _add_nx_graph_node(
        graph: NXGraph, paper: Paper, year_range: Tuple[float, float]
    ) -> None:
        graph.add_node(
            paper.get_id(),
            label=str(paper),
            size=get_size(paper),
            color=hsv_to_hex(*get_hsv(paper.year, year_range)),
        )

    @staticmethod
    def _add_nx_graph_edge(graph: NXGraph, parent: Paper, paper: Paper) -> None:
        graph.add_edge(parent.get_id(), paper.get_id())

    @staticmethod
    def _recursive_create_nx_graph_nodes(
        traverser: "Traverser",
        parent: Paper,
        graph: NXGraph,
        year_range: Tuple[float, float],
    ) -> None:
        for node in traverser.papers.values():
            if node.parent_id == parent.get_id():
                Traverser._add_nx_graph_node(graph, node.paper, year_range)
                Traverser._add_nx_graph_edge(graph, parent, node.paper)

                Traverser._recursive_create_nx_graph_nodes(
                    traverser, node.paper, graph, year_range
                )
