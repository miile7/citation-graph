from collections import defaultdict
from configparser import ConfigParser
from logging import DEBUG, Logger
from typing import DefaultDict, Dict, List, Literal, Optional, TypedDict, Union

from citation_graph.paper import IdType, Paper


REQUEST_TIMEOUT = 10


class _CitationDictEntry(TypedDict):
    papers: list
    offset: int
    limit: int


CitationCache = DefaultDict[Optional[str], _CitationDictEntry]

PaperCache = Dict[Optional[str], Paper]


class DatabaseJsonRepresentation(TypedDict):
    __type: Literal["Database"]
    name: str
    citation_cache: CitationCache
    paper_cache: PaperCache


def _citation_cache_entry_factory() -> _CitationDictEntry:
    return {"papers": [], "offset": 0, "limit": 0}


class Database:
    name: str
    logger: Logger
    idle_time: float
    use_pagination: bool
    page_size: int
    error_count: int
    citation_cache: CitationCache
    paper_cache: PaperCache

    def __init__(
        self,
        name: str,
        logger: Logger,
        idle_time: float,
        use_pagination: bool,
        page_size: int = 100,
        error_count: int = 10,
        citation_cache: Optional[CitationCache] = None,
        paper_cache: Optional[PaperCache] = None,
    ) -> None:
        self.name = name
        self.logger = logger
        self.idle_time = idle_time
        self.use_pagination = use_pagination
        self.page_size = page_size
        self.error_count = error_count

        self.citation_cache = (
            defaultdict(_citation_cache_entry_factory)
            if citation_cache is None
            else citation_cache
        )
        self.paper_cache = {} if paper_cache is None else paper_cache

    def has_all_citation_cache_entries(
        self, paper: Paper, offset: int, limit: int
    ) -> bool:
        paper_id = paper.get_id()
        if paper_id is None:
            return False
        if paper_id not in self.citation_cache:
            return False
        return (
            self.citation_cache[paper_id]["offset"] <= offset
            and self.citation_cache[paper_id]["limit"] >= limit
        )

    def get_citation_cache_entries(
        self, paper: Paper, offset: int, limit: int
    ) -> List[Paper]:
        paper_id = paper.get_id()
        if paper_id is not None:
            ids = self.citation_cache[paper_id]["papers"][offset : offset + limit]
            self.logger.debug(
                f"Found {len(ids)} entries in the cache for {paper} for offset {offset}"
                f" and limit {limit}"
            )
            return [self.paper_cache[id_] for id_ in ids]

        return []

    def cache_paper(self, paper: Paper) -> None:
        self.logger.debug(f"Caching paper {paper}")
        self.paper_cache[paper.get_id()] = paper

    def cache_papers(self, citations: List[Paper]) -> None:
        self.logger.debug(f"Caching papers: {', '.join((str(p) for p in citations))}")
        self.paper_cache.update({c.get_id(): c for c in citations})

    def cache_citations(
        self, parent: Paper, citations: List[Paper], offset: int, limit: int
    ) -> None:
        paper_id = parent.get_id()
        if paper_id is not None:
            self.logger.debug(
                f"Writing {len(citations)} citations of {parent} to cache"
            )
            self.citation_cache[paper_id]["papers"] += list(
                filter(None, (c.get_id() for c in citations))
            )

            if (
                offset + limit < self.citation_cache[paper_id]["offset"]
                or offset > self.citation_cache[paper_id]["limit"]
            ):
                # Corner case, this should never happen: The cached request is from
                # 200-300, the current is from 0-100 (or other way around)
                # -> 100-200 is missing
                # -> forget 200-300, only concurrent areas can be cached
                # This can never happen because the traverser is asking in consecutive
                # steps starting from zero
                self.citation_cache[paper_id]["offset"] = offset
                self.citation_cache[paper_id]["limit"] = limit
            else:
                if offset < self.citation_cache[paper_id]["offset"]:
                    self.citation_cache[paper_id]["offset"] = offset
                if limit > self.citation_cache[paper_id]["limit"]:
                    self.citation_cache[paper_id]["limit"] = limit

            self.cache_papers(citations)

    def wait_before_request(self, paper: Paper, offset: int, limit: int) -> bool:
        if self.paper_is_not_cited_by_database(paper):
            return False
        return not self.has_all_citation_cache_entries(paper, offset, limit)

    def paper_is_not_cited_by_database(self, paper: Paper) -> bool:
        return (
            self.name in paper.expected_citation_count
            and paper.expected_citation_count[self.name] == 0
        )

    async def get_cited_by(self, paper: Paper, offset: int, limit: int) -> List[Paper]:
        """Get all papers that cite the `paper` from the parameters."""
        if self.paper_is_not_cited_by_database(paper):
            self.logger.info(
                f"Skipping request of {paper}, database does not have any citations, "
                "this information was already received when fetching the paper."
            )
            return []

        citations: List[Paper] = []
        cache_citations: List[Paper] = []
        error = False

        try:
            cache_citations = self.get_citation_cache_entries(paper, offset, limit)
        except Exception as e:
            self.logger.exception(e)
            error = True

        if len(cache_citations) > 0:
            self.logger.info(
                f"Loading results ({offset}..{offset + len(cache_citations)}) for "
                f"{paper} from cache"
            )
        elif self.logger.level <= DEBUG:
            self.logger.debug(f"No cached citations found for {paper}")

        if not error and self.has_all_citation_cache_entries(paper, offset, limit):
            return cache_citations
        else:
            self.logger.debug("Extending data from cache with new data")
            citations = await self._get_cited_by(
                paper, offset + len(cache_citations), limit - len(cache_citations)
            )

            self.cache_citations(paper, citations, offset, limit)

        return cache_citations + citations

    async def _get_cited_by(self, paper: Paper, offset: int, limit: int) -> List[Paper]:
        # has to be implemented by child classes
        raise NotImplementedError()

    async def get_paper(self, id_type: IdType, id_: Union[str, int]) -> Paper:
        """Get the paper object for the given `id_`."""
        paper_id = Paper.create_id(id_type, id_)
        if paper_id in self.paper_cache:
            return self.paper_cache[paper_id]

        paper = await self._get_paper(id_type, id_)
        self.cache_paper(paper)
        return paper

    async def _get_paper(self, id_type: IdType, id: Union[str, int]) -> Paper:
        # has to be implemented by child classes
        raise NotImplementedError()

    def toJson(self) -> DatabaseJsonRepresentation:
        return {
            "__type": "Database",
            "name": self.name,
            "citation_cache": self.citation_cache,
            "paper_cache": self.paper_cache,
        }

    def load_settings(self, config: ConfigParser) -> None:
        # has to be implemented by child classes
        pass
