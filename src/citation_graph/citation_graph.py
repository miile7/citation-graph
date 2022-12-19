from asyncio import run as run_async
from argparse import ArgumentParser, Namespace
from csv import writer
from logging import DEBUG, INFO, WARNING, basicConfig, getLogger
from pathlib import Path
from networkx import Graph  # type: ignore[import]
from pyvis.network import Network  # type: ignore[import]
from typing import Iterable, List, Optional, TypedDict
from typing_extensions import Unpack
from citation_graph.cache_manager import CacheManager
from citation_graph.database import Database

from citation_graph.paper import (
    ID_TYPES,
    PAPER_ID_TYPE_SEPARATOR,
    IdType,
    Paper,
    PAPER_ID_LIST_FILE_COMMENT_CHAR,
)
from citation_graph.semantic_scholar import SematicScholarDatabase
from citation_graph.traverser import _PaperNode, Traverser
from citation_graph.utils import SLUG, get_cache_dir, get_valid_filename
from citation_graph.version import get_version


NAME = "Citation Graph"

DEFAULT_LOG_LEVEL = WARNING

DEFAULT_MAX_DEPTH = 1
DEFAULT_POLITENESS_FACTOR = 1
DEFAULT_MAX_CITATIONS_PER_PAPER = 300
DEFAULT_MAX_REQUEST_ERRORS = 10
DEFAULT_ID_TYPE = "doi"
CSV_DELIMITER = ";"


DATABASES: List[Database] = [SematicScholarDatabase()]


logger = getLogger(SLUG)


class ParserArgs(TypedDict, total=False):
    max_depth: int
    clear_cache: bool
    id_type: IdType
    id: str
    max_citations_per_paper: int
    politeness_factor: float
    max_request_errors: int
    excluded_papers: List[str]
    cache_path: Path
    name: str
    create_list: bool
    create_graph: bool
    list_file_name: Optional[str]


def visualize(graph: Graph, filename: str) -> None:
    net = Network(
        height="750px",
        width="100%",
        bgcolor="#222222",
        font_color="white",
        filter_menu=True,
    )
    net.from_nx(graph)
    net.show(filename)


def write_list(nodes: Iterable[_PaperNode], filename: str) -> None:
    with open(filename, "w", encoding="utf-8", newline="") as f:
        w = writer(f, delimiter=CSV_DELIMITER)
        w.writerow((
            "Depth",
            "Parent id",
            "Id",
            "Authors",
            "Title",
            "Year",
            "Citation count (Actually found)",
            "Url",
            "Received citation count",
            "Meta"
        ))

        for node in sorted(nodes, key=lambda n: n.depth):
            paper = node.paper
            w.writerow((
                node.depth,
                node.parent_id,
                paper.get_id(),
                paper.get_authors_str(short=False),
                paper.title,
                paper.year,
                paper.citation_count,
                paper.url,
                paper.temp_citation_count,
                paper.meta
            ))


def get_excluded_papers(excluded_papers: Optional[List[str]]) -> List[Paper]:
    if excluded_papers is None:
        return []

    papers = []
    for excluded_paper in excluded_papers:
        try:
            parsed_paper = Paper.partial_from_string(excluded_paper)
            papers.append(parsed_paper)
        except ValueError:
            paper_path = Path(excluded_paper)
            if paper_path.exists():
                papers += list(Paper.from_file(paper_path, logger))

    return papers


async def run(args: Namespace) -> None:
    start_paper: Optional[Paper] = None
    for database in DATABASES:
        if start_paper is None:
            start_paper = await database.get_paper(args.id_type, args.id)

    if start_paper is None:
        raise Exception(f"Could not find any paper for {args.id_type} {args.id}")

    logger.info(f"Found root paper to be {start_paper}")

    logger.info("Setting up cache file")
    with CacheManager(
        start_paper, DATABASES, args, not args.clear_cache, args.cache_path
    ) as cache_manager:
        logger.info("Starting collection")
        traverser = Traverser(
            start_paper,
            cache_manager.save,
            cache_manager.databases,
            args.max_citations_per_paper,
            args.politeness_factor,
            args.max_request_errors,
            get_excluded_papers(args.excluded_papers),
        )

        await traverser.collect(args.max_depth)

        if args.create_graph:
            logger.info(f"Visualizing result of {start_paper}")
            visualize(
                Traverser.to_nx_graph(traverser),
                args.name.strip()
                if isinstance(args.name, str) and len(args.name) > 0
                else get_valid_filename(f"{start_paper}.html"),
            )

        if args.create_list:
            logger.info(f"Writing list of results of {start_paper}")
            write_list(
                traverser.papers.values(),
                args.list_file_name.strip()
                if isinstance(args.list_file_name, str) and len(args.list_file_name) > 0
                else get_valid_filename(f"{start_paper}.csv"),
            )


def get_arg_parser() -> ArgumentParser:
    parser = ArgumentParser(prog=SLUG, description=f"{NAME} - Create a citation graph")

    parser.add_argument(
        "--version", "-V", action="version", version=f"{NAME}, version {get_version()}"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        dest="log_level",
        help="Set the loglevel to INFO",
        action="store_const",
        const=INFO,
        default=DEFAULT_LOG_LEVEL,
    )
    parser.add_argument(
        "-vv",
        "--very-verbose",
        dest="log_level",
        help="Set the loglevel to DEBUG",
        action="store_const",
        const=DEBUG,
    )
    parser.add_argument(
        "--max-depth",
        "-d",
        dest="max_depth",
        help=(
            "The maximum depth to search papers, if 0, only the root paper is included "
            f"in the result, default is {DEFAULT_MAX_DEPTH}"
        ),
        default=DEFAULT_MAX_DEPTH,
        type=int,
    )
    parser.add_argument(
        "--clear-cache",
        "-c",
        dest="clear_cache",
        help="Clear the cache before fetching. This ensures fresh data.",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--cache-path",
        "-t",
        dest="cache_path",
        help=(
            "The path to load the cache file from and to save it to, default directory "
            f"is {get_cache_dir()}, the name will be the paper id."
        ),
        type=Path,
        default=get_cache_dir(),
    )
    parser.add_argument(
        "--max-citations-per-paper",
        "-m",
        dest="max_citations_per_paper",
        help=(
            "The maximum amount of citations to collect per paper, default is "
            f"{DEFAULT_MAX_CITATIONS_PER_PAPER}"
        ),
        type=int,
        default=DEFAULT_MAX_CITATIONS_PER_PAPER,
    )
    parser.add_argument(
        "--politeness",
        "-p",
        dest="politeness_factor",
        help=(
            "A factor that is multiplied with the idle time that each database "
            "traverser waits between two requests, using values >1 will be more polite "
            "but slow down the requests, values <1 will be faster but may cause your "
            f"IP being blocked, default is {DEFAULT_POLITENESS_FACTOR}"
        ),
        type=float,
        default=DEFAULT_POLITENESS_FACTOR,
    )
    parser.add_argument(
        "--max-request-errors",
        "-e",
        dest="max_request_errors",
        help=(
            "The maximum number of subsequent errors when requesting paper citations. "
            "If more than this specified amount of errors occurs, a (temporary) block "
            "of requests is assumed by the database due to too many requests. The "
            f"default is {DEFAULT_MAX_REQUEST_ERRORS}"
        ),
        type=int,
        default=DEFAULT_MAX_REQUEST_ERRORS,
    )
    parser.add_argument(
        "--exclude-papers",
        "-x",
        dest="excluded_papers",
        help=(
            "Define papers to exclude from the result set, including intermediate "
            "result sets. This allows to prevent fetching citations of papers that are "
            "not relevant for the current research and therefore narrow down the "
            "selection. To define papers, use any id type followed by the id, separated"
            f" by '{PAPER_ID_TYPE_SEPARATOR}', like so: "
            f"{{{'|'.join(ID_TYPES)}}}{PAPER_ID_TYPE_SEPARATOR}PAPER_ID. "
            "Alternatively a path to a file can be given where the paper ids are "
            "listed, each paper id in a separate line. Lines starting with a "
            f"'{PAPER_ID_LIST_FILE_COMMENT_CHAR}'-charcter are treated as comments and "
            "are ignored entirely."
        ),
        type=str,
        nargs="*",
    )
    parser.add_argument(
        "--list",
        "-l",
        dest="create_list",
        help=("Output a list containing the papers, ordered by their level."),
        action="store_true",
        default=False
    )
    parser.add_argument(
        "--list-file-name",
        "-n",
        dest="list_file_name",
        help=(
            "The file name of the list file, by default the authors and the year are "
            "the file name. The file is created in the current working directory"
        ),
        default=None,
        type=str
    )
    parser.add_argument(
        "--no-graph",
        "-g",
        dest="create_graph",
        help="Use to prevent creating a visualization graph",
        action="store_false",
        default=True
    )

    parser.add_argument(
        "id_type",
        nargs="?",
        help=f"The id type, default is {DEFAULT_ID_TYPE}",
        choices=ID_TYPES,
        default=DEFAULT_ID_TYPE,
    )
    parser.add_argument(
        "id",
        help=(
            f"The id of the paper to use as the root, by default an {DEFAULT_ID_TYPE}"
            " is assumed, this can be changed with the ID_TYPE parameter"
        ),
        type=str,
    )
    parser.add_argument(
        "name",
        help=(
            "The name of the graph output html file, if not given, it will be in the "
            "current working directory with the authors and the year as the file name."
        ),
        type=str,
        nargs="?",
        default=None
    )

    return parser


def init_logging(args: Namespace) -> None:
    if args.log_level < INFO:
        log_format = "[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
    else:
        log_format = "%(levelname)s: %(message)s"

    basicConfig(level=args.log_level, format=log_format, datefmt="%Y-%m-%d %H:%M:%S")


def main(**kwargs: Unpack[ParserArgs]) -> None:
    parser = get_arg_parser()
    if len(kwargs) > 0:
        args = Namespace(**kwargs)
    else:
        args = parser.parse_args()

    init_logging(args)

    run_async(run(args))


if __name__ == "__main__":
    main()
