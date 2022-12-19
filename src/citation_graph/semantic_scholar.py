from logging import getLogger
from requests import get
from typing import Any, Dict, Generator, List, Optional, TypedDict, Union, cast
from citation_graph.database import REQUEST_TIMEOUT, Database

from citation_graph.paper import AuthorName, IdType, Paper


class _ResultJSONExternalIds(TypedDict, total=False):
    DBLP: str
    ArXiv: str
    DOI: str
    CorpusId: int
    PubMedCentral: str
    PubMed: str


class _ResultJSONAuthors(TypedDict):
    authorId: str
    name: str


class _ResultJSONPaper(TypedDict):
    paperId: str
    externalIds: _ResultJSONExternalIds
    title: str
    year: int
    authors: List[_ResultJSONAuthors]
    citationCount: int


class _ResultJSONData(TypedDict):
    citingPaper: _ResultJSONPaper


class _ResultJSON(TypedDict):
    offset: int
    next: int
    data: List[_ResultJSONData]


class SematicScholarDatabase(Database):
    paper_base_url = "https://www.semanticscholar.org/paper"
    api_base_url = "https://api.semanticscholar.org/graph/v1/paper"
    params = {
        "fields": ",".join(("title", "year", "authors", "externalIds", "citationCount"))
    }

    def __init__(self) -> None:
        logger = getLogger(
            "citation_graph.semantic_scholar.SemanticScholarTraverser"
        )
        super().__init__(
            "semanticscholar.org",
            logger,
            5 * 60 / 100,  # 100 requests per five minutes
            True,
            100,
            10
        )

    def wait_before_request(self, paper: Paper, offset: int, limit: int) -> bool:
        if not self.is_paper_cited_by_database(paper):
            return False
        return super().wait_before_request(paper, offset, limit)

    def get_paper_url(self, paper: Paper) -> str:
        return self.get_paper_url_by_id(paper.get_id_type(), paper.get_raw_id())

    def get_paper_url_by_id(
        self, id_type: Optional[IdType], id: Union[str, int, None]
    ) -> str:
        if id is None:
            raise KeyError("Ids of type None are invalid")

        if id_type == "doi":
            url_id = id
        elif id_type == "arxiv":
            url_id = f"arXiv:{id}"
        elif id_type == "corpus_id":
            url_id = f"CorpusID:{id}"
        else:
            raise KeyError(
                "Cannot find an identifier that is supported by the current database."
            )
        return f"{self.api_base_url}/{url_id}"

    async def _get_paper(self, id_type: IdType, id: Union[str, int]) -> Paper:
        url = self.get_paper_url_by_id(id_type, id)
        self.logger.info(f"Fetching paper for {id_type} {id} by url {url}")

        result = get(url, self.params, timeout=REQUEST_TIMEOUT)
        r = result.json()

        if not isinstance(r, dict):
            raise ValueError(f"Could not find information for paper with id {id}")

        return self._parse_json_result_paper(cast(_ResultJSONPaper, r))

    def _parse_json_result_paper(self, result: _ResultJSONPaper) -> Paper:
        try:
            paper = Paper(
                list(SematicScholarDatabase._parse_author_names(result["authors"])),
                result["year"],
                result["title"],
            )
            paper.url = f"{self.paper_base_url}/{result['paperId']}"
            paper.meta[self.name] = {"citation_count": result["citationCount"]}
        except KeyError:
            raise ValueError(f"Cannot parse json {result}")

        try:
            paper.set_external_id(
                cast(
                    Dict[str, Union[str, int, None]],
                    result["externalIds"],
                )
            )
        except KeyError:
            pass

        return paper

    def get_citing_papers_url(self, paper: Paper) -> str:
        return f"{self.get_paper_url(paper)}/citations"

    def is_paper_cited_by_database(self, paper: Paper) -> bool:
        return (
            self.name not in paper.meta
            or "citation_count" not in paper.meta[self.name]
            or paper.meta[self.name]["citation_count"] != 0
        )

    async def _get_cited_by(self, paper: Paper, offset: int, limit: int) -> List[Paper]:
        if not self.is_paper_cited_by_database(paper):
            self.logger.info(
                f"Skipping request of {paper}, database does not have any citations, "
                "this information was already received when fetching the paper."
            )
            return []

        try:
            url = self.get_citing_papers_url(paper)
        except KeyError:
            self.logger.info(
                f"Skipping {paper}, cannot find an identifier for database requests"
            )
            return []

        params: Dict[str, Any] = self.params.copy()
        params["offset"] = offset
        # load more for caching, this is the same request and does not have any
        # penalty from the database concerning requests
        params["limit"] = max(limit, self.page_size)

        self.logger.info(
            f"Fetching results ({offset}..{offset + limit}) for {paper} from {url} "
            f"(actually loading {params['limit']} results for cache"
        )
        result = get(url, params, timeout=REQUEST_TIMEOUT)

        r = result.json()
        if (
            not isinstance(r, dict)
            or "data" not in r
            or not isinstance(r["data"], list)
        ):
            raise ValueError(f"Cannot parser the returned json data: \n\n{result.text}")

        self.logger.debug(f"Parsing result of {paper}")

        cited_by_papers = self._parse_json_result_citing_paper(cast(_ResultJSON, r))

        self.logger.debug(f"Found {len(cited_by_papers)} citations of {paper}")

        if len(cited_by_papers) > limit:
            self.logger.debug(
                f"Caching last {len(cited_by_papers) - limit} elements for later use, "
                f"returning only the first {limit} elements as requested."
            )
            cache_only = cited_by_papers[limit:]
            self.cache_citations(paper, cache_only)

            cited_by_papers = cited_by_papers[:limit]

        return cited_by_papers

    def _parse_json_result_citing_paper(self, result: _ResultJSON) -> List[Paper]:
        papers: List[Paper] = []
        for citing_paper in result["data"]:
            papers.append(self._parse_json_result_paper(citing_paper["citingPaper"]))

        return papers

    @staticmethod
    def _parse_author_names(
        authors: List[_ResultJSONAuthors],
    ) -> Generator[AuthorName, None, None]:
        for author in authors:
            names = author["name"].split(" ", 1)
            yield AuthorName(forename=names[0], lastname=names[-1])
