from asyncio import gather, sleep
from dataclasses import dataclass
from logging import getLogger
from random import random
from typing import (
    Dict,
    Generator,
    Generic,
    List,
    NamedTuple,
    Optional,
    TypeVar,
    TypedDict,
)

from citation_graph.paper import Paper


class _PaperNode(NamedTuple):
    depth: int
    paper: Paper
    parent_doi: Optional[str]


_T = TypeVar("_T")


@dataclass
class _GraphNode(Generic[_T]):
    node: _T
    children: List["_GraphNode[_T]"]


Graph = _GraphNode


class MetaData(TypedDict, total=False):
    idle_time: float  # idle time in seconds between two requests


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
        for node in self.papers.values():
            if node.depth == level:
                yield node.paper

    def _register_cited_by(self, level: int, paper: Paper, parent: Paper) -> bool:
        if paper.doi in self.papers:
            return False

        self._add_paper_node(level, paper, parent.doi)
        return True

    async def _collect_papers_for_next_level(self, current_level: int) -> None:
        if "idle_ime" in self.metadata and self.metadata["idle_time"] > 0:
            # prevent spawning all requests at the same time
            await sleep(random() * self.metadata["idle_time"])

        for parent in self._iter_papers_for_level(current_level):
            self.logger.debug(f"Finding citations of {parent}")

            if "idle_ime" in self.metadata and self.metadata["idle_time"] > 0:
                await sleep(self.metadata["idle_time"])

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
            tasks.append(self._collect_papers_for_next_level(self._depth))

        gather(*tasks)

    async def _get_cited_by(self, paper: Paper) -> List[Paper]:
        """Get all papers that cite the `paper` from the parameters."""
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
            if node.parent_doi == parent.doi:
                children.append(
                    Traverser._recursive_create_graph_nodes(traverser, node.paper)
                )

        return _GraphNode(parent, children)
