from collections import OrderedDict
from logging import Logger
from typing import Dict, cast
import pytest

from citation_graph.database import Database
from citation_graph.paper import ID_TYPES, AuthorName, IdType, Paper
from tests.utils import mocked_logger


DATABASE_NAME = "test-database"
IDLE_TIME = 2
USE_PAGINATION = True
TEST_PAPER_LIST = [
    Paper(
        [AuthorName(chr(65 + j), chr(97 + j)) for j in range(i + 1)],
        i + 1990,
        f"Test paper {i + 1}",
        OrderedDict(**{ID_TYPES[i % len(ID_TYPES)]: f"test-id-{i}"}),
    )
    for i in range(20)
]
PAPER_CITATION_NUMBER = 3


@pytest.fixture()
def database(mocked_logger: Logger) -> Database:
    db = Database(DATABASE_NAME, mocked_logger, IDLE_TIME, USE_PAGINATION)

    for i, paper in enumerate(TEST_PAPER_LIST):
        db._paper_cache[paper.get_id()] = paper

        if i % PAPER_CITATION_NUMBER == 0 and i > 0:
            db._citation_cache[paper.get_id()] = {
                "papers": TEST_PAPER_LIST[i - PAPER_CITATION_NUMBER : i],
                "offset": 0,
                "limit": PAPER_CITATION_NUMBER,
            }

    return db


def test_has_all_citation_cache_entries(database: Database) -> None:
    database.has_all_citation_cache_entries()
