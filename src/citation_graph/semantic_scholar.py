from logging import getLogger
from requests import get
from typing import List, TypedDict

from citation_graph.paper import AuthorName, Paper
from citation_graph.traverser import Traverser


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


class _ResultJSONData(TypedDict):
    citingPaper: _ResultJSONPaper


class _ResultJSON(TypedDict):
    offset: int
    next: int
    data: List[_ResultJSONData]


class SematicScholarTraverser(Traverser):
    paper_base_url = "https://www.semanticscholar.org/paper"
    url = "https://api.semanticscholar.org/graph/v1/paper"
    params = {"fields": ",".join(("title", "year", "authors", "externalIds"))}

    def __init__(self) -> None:
        super().__init__()

        self.logger = getLogger(
            "citation_graph.semantic_scholar.SemanticScholarTraverser"
        )

    def get_rul(self, doi: str) -> str:
        return f"{self.url}/{doi}/citations"

    async def _get_cited_by(self, paper: Paper) -> List[Paper]:
        url = self.get_rul(paper.doi)
        self.logger.info(f"Fetching result for {paper} from {url}")

        result = get(url, self.params)

        r = result.json()
        assert isinstance(r, dict)
        # assert isinstance(r, _ResultJSON)

        papers: List[Paper] = []
        for citing_paper in r["data"]:
            papers.append(
                Paper(
                    [
                        AuthorName(*a["name"].split(" ", 1))
                        for a in citing_paper["citingPaper"]["authors"]
                    ],
                    citing_paper["citingPaper"]["year"],
                    citing_paper["citingPaper"]["title"],
                    citing_paper["citingPaper"]["externalIds"]["DOI"],
                    f"{self.paper_base_url}/{citing_paper['citingPaper']['paperId']}",
                )
            )

        return papers
