from collections import OrderedDict
from dataclasses import dataclass, field
from logging import Logger
from math import ceil
from pathlib import Path
from Levenshtein import distance
from re import compile
from typing import Any, Dict, Generator, List, Literal, Optional, Tuple, Union, get_args


WORD_BOUNDARIES_REG = compile(r"[\b]+")
"""
`ceil(LEVESHTEIN_SIMILAR_DISTANCE_FACTOR * <chars in the paper title>) - 1` characters
may differ when comparing two paper titles to still treat them as the same title
"""
LEVESHTEIN_SIMILAR_DISTANCE_FACTOR = 0.02
PAPER_ID_TYPE_SEPARATOR = "::"
MISSING_TITLE = "{{MISSING_TITLE}}"
PAPER_ID_LIST_FILE_COMMENT_CHAR = "#"


IdType = Literal["doi", "dblp", "arxiv", "corpusid"]


ID_TYPES: Tuple[IdType, ...] = get_args(IdType)


@dataclass
class AuthorName:
    forename: str
    lastname: str

    def __hash__(self) -> int:
        return hash(f"{self.forename}{self.lastname}")


@dataclass
class Paper:
    authors: List[AuthorName]
    year: int
    title: str
    ids: OrderedDict[IdType, Union[str, int]] = field(default_factory=OrderedDict)
    url: Optional[str] = None
    citation_count: Optional[int] = None
    expected_citation_count: Optional[int] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def get_authors_str(self, short=False) -> str:
        authors = [
            f"{a.forename} {a.lastname}" if not short else a.lastname
            for a in self.authors
        ]

        if len(authors) > 2:
            if short:
                return f"{authors[0]} et al."
            return f"{', '.join(authors[:-1])} and {authors[-1]}"
        elif len(authors) == 2:
            return f"{authors[0]} and {authors[1]}"
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
            return Paper.create_id(*self._get_id())
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
        for id_type, id_ in self.ids.items():
            if id_ is not None:
                return id_type, id_

        raise KeyError("No id found")

    def set_external_id(self, external_ids: Dict[str, Union[str, int, None]]) -> None:
        ids = {}
        for name, external_id in external_ids.items():
            if external_id is None:
                continue

            ids[Paper.normalize_external_id(name)] = external_id

        # order is important
        for name in ID_TYPES:
            if name in ids:
                self.ids[name] = ids[name]

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, Paper):
            return False

        for id_type, id_ in self.ids.items():
            if (
                id_type in o.ids
                and o.ids[id_type] is not None
                and o.ids[id_type] == id_
            ):
                return True

        if o.title == MISSING_TITLE or self.title == MISSING_TITLE:
            return False

        if (
            o.year == self.year
            and set(o.authors) == set(self.authors)
            and Paper.titles_resemble(o.title, self.title)
        ):
            return True

        return False

    @staticmethod
    def partial_from_string(paper_def: str) -> "Paper":
        paper_split = paper_def.strip().split(PAPER_ID_TYPE_SEPARATOR, 1)

        if len(paper_split) != 2:
            raise ValueError(
                f"Cannot parse paper definition '{paper_def}', the id type and the id "
                f"must be separated by '{PAPER_ID_TYPE_SEPARATOR}'."
            )

        id_type, id_ = paper_split

        if id_type not in ID_TYPES:
            raise ValueError(
                f"The id type '{id_type}' of paper definition '{paper_def}' is invalid."
                f" Supported types are {', '.join(ID_TYPES)}."
            )

        if id_ == "":
            raise ValueError("The id of paper definition '{paper_def}' is empty.")

        paper = Paper([], 0, MISSING_TITLE)
        paper.set_external_id({id_type: id_})

        return paper

    @staticmethod
    def create_id(id_type: IdType, id_: Union[str, int]) -> str:
        return f"{id_type}{PAPER_ID_TYPE_SEPARATOR}{id_}"

    @staticmethod
    def _normalize_title(title: str) -> str:
        return WORD_BOUNDARIES_REG.sub(
            " ",  # remove punctuation
            title.encode("utf-8").decode("ascii", errors="replace"),  # remove non-ascii
        )

    @staticmethod
    def titles_resemble(title1: str, title2: str) -> bool:
        normalized_title_1 = Paper._normalize_title(title1)
        normalized_title_2 = Paper._normalize_title(title2)

        threshold = ceil(
            min(len(normalized_title_1), len(normalized_title_2))
            * LEVESHTEIN_SIMILAR_DISTANCE_FACTOR
        )

        return distance(normalized_title_1, normalized_title_2) < threshold

    @staticmethod
    def normalize_external_id(id_name: str) -> str:
        return WORD_BOUNDARIES_REG.sub("", id_name.lower().strip())

    @staticmethod
    def from_file(
        file_path: Path, logger: Logger, encoding: str = "utf-8", **kwargs
    ) -> Generator["Paper", None, None]:
        if file_path.exists():
            with open(file_path, "r", encoding=encoding, **kwargs) as f:
                for i, raw_line in enumerate(f):
                    line = raw_line.strip()

                    if line.startswith(PAPER_ID_LIST_FILE_COMMENT_CHAR):
                        continue

                    try:
                        yield Paper.partial_from_string(raw_line)
                    except ValueError as e:
                        logger.warning(
                            f"Cannot parse paper definition in line {i + 1}: {str(e)}"
                        )
