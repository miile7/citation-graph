from dataclasses import dataclass, field
from re import compile
from typing import Any, Dict, List, Literal, Optional, Tuple, Union


WORD_BOUNDARIES_REG = compile(r"[\b]+")


@dataclass
class AuthorName:
    forename: str
    lastname: str


IdType = Literal["doi", "dblp", "arxiv", "corpus_id"]


@dataclass
class Paper:
    authors: List[AuthorName]
    year: int
    title: str
    doi: Optional[str] = None
    dblp: Optional[str] = None
    arxiv: Optional[str] = None
    corpus_id: Optional[int] = None
    url: Optional[str] = None
    citation_count: Optional[int] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def get_authors_str(self, short=False) -> str:
        authors = [
            f"{a.forename} {a.lastname}"
            if not short
            else a.lastname
            for a in self.authors
        ]

        if len(authors) > 2:
            if short:
                return f"{authors[0]} et al."
            return f"{', '.join(authors[:-1])} and {authors[-1]}"
        elif len(authors) == 2:
            return (
                f"{authors[0]} and {authors[1]}"
            )
        elif len(authors) == 1:
            return authors[0]
        else:
            return ""


    def __str__(self) -> str:
        if len(self.authors) > 0:
            return f"{self.get_authors_str(True)} {self.year}"
        else:
            return f"{self.get_id()} {self.year}"

    def get_id(self) -> Optional[str]:
        try:
            type, id = self._get_id()
            return f"{type}::{id}"
        except KeyError:
            return None

    def get_id_type(self) -> Optional[IdType]:
        try:
            id_type, _ = self._get_id()
            return id_type
        except KeyError:
            return None

    def get_raw_id(self) -> Optional[Union[str, int]]:
        try:
            _, id = self._get_id()
            return id
        except KeyError:
            return None

    def _get_id(self) -> Tuple[IdType, Union[str, int]]:
        if self.doi is not None:
            return "doi", self.doi
        elif self.dblp is not None:
            return "dblp", self.dblp
        elif self.arxiv is not None:
            return "arxiv", self.arxiv
        elif self.corpus_id is not None:
            return "corpus_id", self.corpus_id
        else:
            raise KeyError("No id found")

    def set_external_id(self, external_ids: Dict[str, Union[str, int, None]]) -> None:
        for name, external_id in external_ids.items():
            if external_id is None:
                continue

            id_name = Paper.normalize_external_id(name)

            if id_name == "doi":
                self.doi = str(external_id)
            elif id_name == "dblp":
                self.dblp = str(external_id)
            elif id_name == "arxiv":
                self.arxiv = str(external_id)
            elif id_name == "corpusid":
                self.corpus_id = int(external_id)

    @staticmethod
    def normalize_external_id(id_name: str) -> str:
        return WORD_BOUNDARIES_REG.sub("", id_name.lower().strip())
