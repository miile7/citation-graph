from collections import OrderedDict
from typing import List
import pytest

from citation_graph.paper import (
    AuthorName,
    ID_TYPES,
    IdType,
    Paper,
    PAPER_ID_TYPE_SEPARATOR,
)


@pytest.fixture()
def paper() -> Paper:
    return Paper(
        [AuthorName("Jane", "Doe"), AuthorName("Matti", "Meikäläinen")],
        2022,
        "Test Paper",
    )


@pytest.mark.parametrize(
    "authors, long_authors, short_authors",
    [
        ([AuthorName("Jane", "Doe")], "Jane Doe", "Doe"),
        (
            [AuthorName("Jane", "Doe"), AuthorName("Matti", "Meikäläinen")],
            "Jane Doe and Matti Meikäläinen",
            "Doe and Meikäläinen",
        ),
        (
            [
                AuthorName("Jane", "Doe"),
                AuthorName("Matti", "Meikäläinen"),
                AuthorName("Pinco", "Pallino"),
            ],
            "Jane Doe, Matti Meikäläinen and Pinco Pallino",
            "Doe et al.",
        ),
    ],
)
def test_authors_str(
    authors: List[AuthorName], long_authors: str, short_authors: str
) -> None:
    paper = Paper(authors, 2022, "Test Paper")

    assert paper.get_authors_str(short=False) == long_authors
    assert paper.get_authors_str(short=True) == short_authors


@pytest.mark.parametrize("id_type", ID_TYPES)
def test_external_ids(paper: Paper, id_type: IdType) -> None:
    id_value = "id_value"
    id_dict = {id_type: id_value}
    paper.set_external_id(id_dict)

    assert paper.get_id_type() == id_type
    assert paper.get_id() == f"{id_type}{PAPER_ID_TYPE_SEPARATOR}{id_value}"
    assert paper.get_raw_id() == id_value
    assert paper._get_id() == (id_type, id_value)


@pytest.mark.parametrize("title, expected_title", [("á", "a")])
def test_normalize_title(title: str, expected_title: str) -> None:
    assert Paper._normalize_title(title) == expected_title


@pytest.mark.parametrize(
    "title1, title2",
    [
        ("This is a test", "This is a test"),
        ("this is A test", "This is a test"),
        ("This, is: A test", "This is a test"),
        ("This ís á tést", "This is a test"),
        (
            "This is $\\alpha$ tést with some more words to have a realistic length",
            "This is a test with some more words to have a realistic length",
        ),
    ],
)
def test_titles_resemble(title1: str, title2: str) -> None:
    assert Paper.titles_resemble(title1, title2)


@pytest.mark.parametrize(
    "title1, title2",
    [
        ("This is not a test", "This is a test"),
        ("This a test is", "This is a test"),
    ],
)
def test_titles_do_not_resemble(title1: str, title2: str) -> None:
    assert not Paper.titles_resemble(title1, title2)


@pytest.mark.parametrize(
    "paper1, paper2",
    [
        (
            Paper(
                [AuthorName("A", "B"), AuthorName("C", "D")],
                2022,
                "This is a test",
                OrderedDict({"doi": "1234"}),
            ),
            Paper(
                [AuthorName("A", "B"), AuthorName("C", "D")],
                2022,
                "This is a test",
                OrderedDict({"doi": "1234"}),
            ),
        ),
        (
            Paper(
                [AuthorName("A", "B"), AuthorName("C", "D")],
                2022,
                "This is a test",
                OrderedDict({"doi": "5678"}),
            ),
            Paper(
                [AuthorName("A", "B"), AuthorName("C", "D")],
                2022,
                "This is a test",
                OrderedDict({"doi": "1234"}),
            ),
        ),
        (
            Paper([AuthorName("A", "B"), AuthorName("C", "D")], 2022, "This is a test"),
            Paper([AuthorName("A", "B"), AuthorName("C", "D")], 2022, "This is a test"),
        ),
    ],
)
def test_similar(paper1: Paper, paper2: Paper) -> None:
    assert paper1 == paper2


@pytest.mark.parametrize(
    "paper1, paper2",
    [
        (
            Paper([AuthorName("A", "B"), AuthorName("C", "D")], 2022, "This is a test"),
            Paper([AuthorName("A", "B"), AuthorName("C", "E")], 2022, "This is a test"),
        ),
        (
            Paper([AuthorName("A", "B"), AuthorName("C", "D")], 2022, "This is a test"),
            Paper([AuthorName("A", "B"), AuthorName("C", "D")], 2020, "This is a test"),
        ),
        (
            Paper([AuthorName("A", "B"), AuthorName("C", "D")], 2022, "This is a test"),
            Paper(
                [AuthorName("A", "B"), AuthorName("C", "D")], 2022, "This is not a test"
            ),
        ),
    ],
)
def test_different(paper1: Paper, paper2: Paper) -> None:
    assert paper1 != paper2
