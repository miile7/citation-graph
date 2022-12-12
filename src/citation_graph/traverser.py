from asyncio import create_task, sleep
from dataclasses import dataclass
from logging import getLogger
from typing import Coroutine, Dict, Generator, Generic, List, NamedTuple, Optional, Tuple, TypeVar, TypedDict

from citation_graph.paper import Paper


_PAPER_NODE_LEVEL_INDEX = 0
_PAPER_NODE_PAPER_INDEX = 1
_PAPER_NODE_PARENT_INDEX = 2


class _PaperNode(NamedTuple):
    depth: int
    paper: Paper
    parent_doi: Optional[str]


_T = TypeVar("_T")


@dataclass
class _GraphNode(Generic[_T]):
    node: _T
    children: List["_GraphNode[_T]"]


class Graph(_GraphNode):
    pass


class MetaData(TypedDict, total=False):
    idle_time: int  # idle time in seconds between two requests


class Traverser:
    metadata: MetaData

    max_depth: int
    start_paper: Paper
    papers: Dict[str, _PaperNode]
    _depth: int

    def __init__(self) -> None:
        self.logger = getLogger("citation_graph.traverser.Traverser")
        self.logger.debug("Initialize traverser object")
        self.metadata = MetaData()

    def _add_paper_node(
        self, level: int, paper: Paper, parent_doi: Optional[str]
    ) -> None:
        self.papers[paper.doi] = _PaperNode(level, paper, parent_doi)

    def _iter_papers_for_level(self, level: int) -> Generator[Paper, None, None]:
        for paper in self.papers.values():
            if paper[_PAPER_NODE_LEVEL_INDEX] == level:
                p = paper[_PAPER_NODE_PAPER_INDEX]
                assert isinstance(p, Paper)  # for mypy
                yield p

    def _register_cited_by(self, level: int, paper: Paper, parent: Paper) -> bool:
        if paper.doi in self.papers:
            return False

        self._add_paper_node(level, paper, parent.doi)
        return True

    async def _collect_papers_for_next_level(self, current_level: int) -> None:
        for parent in self._iter_papers_for_level(current_level):
            self.logger.debug(f"Finding citations of {parent}")
            cited_by_papers = await self._get_cited_by(parent)

            self.logger.debug(f"Found {len(cited_by_papers)} citations of {parent}")
            for paper in cited_by_papers:
                self._register_cited_by(current_level + 1, paper, parent)

    async def collect(self, start_paper: Paper, max_depth: int) -> None:
        self.max_depth = max_depth
        self.start_paper = start_paper
        self.papers = {}
        self._add_paper_node(0, self.start_paper, None)

        self.logger.debug(
            f"Collecting citations until depth of {max_depth} for paper {start_paper}."
        )

        tasks = []
        for self._depth in range(self.max_depth):
            self.logger.debug(f"Performing step {self._depth}")
            tasks.append(create_task(self._collect_papers_for_next_level(self._depth)))

            if "idle_ime" in self.metadata and self.metadata["idle_time"] > 0:
                sleep(self.metadata["idle_time"])

        for task in tasks:
            await task

    async def _get_cited_by(self, paper: Paper) -> List[Paper]:
        """Get all papers that cite the `paper` from the parameters."""
        raise NotImplementedError()

    @classmethod
    def to_list(traverser: "Traverser") -> List[Paper]:
        if len(traverser.papers) <= 1:
            raise Exception("Run Traverser.collect() before parsing to a list.")

        return [
            node[_PAPER_NODE_PAPER_INDEX] for node in
            sorted(
                traverser.papers.values(),
                key=lambda node: node[_PAPER_NODE_LEVEL_INDEX]
            )
        ]

    @classmethod
    def to_graph(traverser: "Traverser") -> Graph[Paper]:
        if len(traverser.papers) <= 1:
            raise Exception("Run Traverser.collect() before parsing to a list.")

        root: Optional[Paper] = None
        for paper in traverser.papers:
            if paper[_PAPER_NODE_LEVEL_INDEX] == 0:
                root = paper
                break

        if root is None:
            raise Exception("Could not find root paper.")

        return Traverser._recursive_create_graph_nodes(traverser, root)

    @classmethod
    def _recursive_create_graph_nodes(
        traverser: "Traverser", parent: Paper
    ) -> _GraphNode[Paper]:
        children: List[_GraphNode[Paper]] = []

        for paper in traverser.papers:
            if paper[_PAPER_NODE_PARENT_INDEX] == parent.doi:
                children.append(Traverser._recursive_create_graph_nodes(
                    traverser, paper[_PAPER_NODE_PAPER_INDEX]
                ))

        return _GraphNode(parent, children)

