from asyncio import gather, run as run_async
from argparse import ArgumentParser, Namespace
from logging import DEBUG, INFO, WARNING, basicConfig, getLogger
from networkx import Graph  # type: ignore[import]
from pyvis.network import Network  # type: ignore[import]
from typing import List, Optional, Type, TypedDict
from typing_extensions import Unpack
from citation_graph.caching import is_cached, load_cached, save_cache

from citation_graph.paper import Paper
from citation_graph.semantic_scholar import SematicScholarTraverser
from citation_graph.traverser import Traverser
from citation_graph.utils import SLUG, get_valid_filename
from citation_graph.version import get_version


NAME = "Citation Graph"

DEFAULT_LOG_LEVEL = WARNING

DEFAULT_MAX_DEPTH = 1
DEFAULT_POLITENESS_FACTOR = 1
DEFAULT_MAX_CITATIONS_PER_PAPER = 300

TRAVERSER: List[Type[Traverser]] = [SematicScholarTraverser]


logger = getLogger(SLUG)


class ParserArgs(TypedDict, total=False):
    depth: int
    clear_cache: bool
    doi: str
    max_citations_per_paper: int
    politeness_factor: float


def visualize(graph: Graph, filename: str) -> None:
    net = Network()
    net.from_nx(graph)
    net.show(filename)


def save_callback(
    start_paper: Optional[Paper], traversers: List[Traverser], args: Namespace
) -> None:
    # This function exists for mypy only, start_paper is never None, otherwise the
    # program aborts with an error before this function is ever executed
    if start_paper is not None:
        save_cache(start_paper, traversers, args)


async def run(args: Namespace) -> None:
    start_paper: Optional[Paper] = None
    traversers: List[Traverser] = []
    for traverser_class in TRAVERSER:
        traverser = traverser_class(
            save_callback=lambda: save_callback(start_paper, traversers, args),
            max_citations_per_paper=args.max_citations_per_paper,
            politeness_factor=args.politeness_factor,
        )
        traversers.append(traverser)

        if start_paper is None:
            try:
                start_paper = await traverser.get_paper("doi", args.doi)
            except ValueError:
                pass

    if start_paper is None:
        raise Exception(f"Could not find any paper for DOI {args.doi}")

    logger.info(f"Found root paper to be {start_paper}")

    if args.clear_cache:
        logger.debug("Ignoring cache because of --clear-cache")
    elif is_cached(start_paper):
        load_cached(start_paper, traversers)

    tasks = []
    for traverser in traversers:
        logger.info(f"Kick off collection from {traverser}")
        tasks.append(traverser.resume_collection(start_paper, args.max_depth))

        logger.debug("Waiting for all traversers to complete.")
        await gather(*tasks)

    for traverser in traversers:
        logger.info(f"Visualizing result of {traverser}")
        visualize(
            Traverser.to_nx_graph(traverser),
            get_valid_filename(f"{start_paper} - {traverser.name}.html"),
        )


def get_arg_parser() -> ArgumentParser:
    parser = ArgumentParser(prog=NAME)

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

    parser.add_argument("doi", help="The DOI of the paper to use as the root", type=str)

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
