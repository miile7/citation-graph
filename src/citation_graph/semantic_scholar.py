from configparser import ConfigParser
from logging import getLogger
from typing import Any, Dict, Generator, List, Optional, TypedDict, Union, cast

from citation_graph.restful_database import RestfulDatabase
from citation_graph.paper import AuthorName, Paper


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


class SematicScholarDatabase(RestfulDatabase[_ResultJSONPaper, _ResultJSON]):
    api_key: Optional[str] = None

    paper_base_url = "https://www.semanticscholar.org/paper"

    def __init__(self) -> None:
        logger = getLogger("citation_graph.semantic_scholar.SemanticScholarTraverser")

        super().__init__(
            "semanticscholar.org",
            logger,
            paper_api_url="https://api.semanticscholar.org/graph/v1/paper/{id}",
            citation_api_url=(
                "https://api.semanticscholar.org/graph/v1/paper/{id}/citations"
            ),
            api_params={
                "fields": ",".join(
                    ("title", "year", "authors", "externalIds", "citationCount")
                )
            },
            id_formats={
                "doi": "{id}",
                "arxiv": "arXiv:{id}",
                "corpusid": "CorpusID:{id}",
            },
            idle_time=5 * 60 / 100,  # 100 requests per five minutes
            use_pagination=True,
            page_size=100,
        )

    def init_headers(self) -> Dict[str, Any]:
        # if self.api_key is not None:
        #     return {"x-api-key": self.api_key}

        return {}

    def _parse_json_result_paper(self, result: _ResultJSONPaper) -> Paper:
        try:
            paper = Paper(
                list(SematicScholarDatabase._parse_author_names(result["authors"])),
                result["year"],
                result["title"],
            )
            paper.url = f"{self.paper_base_url}/{result['paperId']}"
            paper.set_expected_citation_count(self.name, result["citationCount"])
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
            self.logger.warning(
                f"Cannot find an external id for {paper}, json result does not contain "
                f"a known id definition: {result['externalIds']}"
            )

        return paper

    def _parse_json_result_citing_paper(self, result: _ResultJSON) -> List[Paper]:
        papers: List[Paper] = []
        for citing_paper in result["data"]:
            papers.append(self._parse_json_result_paper(citing_paper["citingPaper"]))

        return papers

    def load_settings(self, config: ConfigParser) -> None:
        if self.name in config:
            self.api_key = config.get(self.name, "api_key", fallback=None)
            if self.api_key is not None:
                self.logger.info(
                    f"Found API key for {self.name}: {'*' * len(self.api_key)}"
                )

            if self.api_key is not None:
                requests_per_second = config.get(
                    self.name, "api_requests_per_second", fallback=None
                )
                if isinstance(requests_per_second, int):
                    self.idle_time = max(1 / requests_per_second, 0.01)
                    self.logger.info(
                        f"Decreasing idle time of {self.name} to {self.idle_time}s "
                        f"because API key {requests_per_second} requests per second are"
                        " supported."
                    )

    @staticmethod
    def _parse_author_names(
        authors: List[_ResultJSONAuthors],
    ) -> Generator[AuthorName, None, None]:
        for author in authors:
            names = author["name"].split(" ", 1)
            yield AuthorName(forename=names[0], lastname=names[-1])
