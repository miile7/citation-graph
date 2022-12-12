from asyncio import gather, run as run_async
from argparse import ArgumentParser, Namespace
from logging import DEBUG, INFO, WARNING, basicConfig, getLogger
from typing import List, TypedDict
from typing_extensions import Unpack

from citation_graph.paper import AuthorName, Paper
from citation_graph.semantic_scholar import SematicScholarTraverser
from citation_graph.traverser import Traverser
from citation_graph.version import get_version


NAME = "Citation Graph"

DEFAULT_LOG_LEVEL = WARNING

DEFAULT_MAX_DEPTH = 2

TRAVERSER: List[Traverser] = [
    SematicScholarTraverser()
]


logger = getLogger("citation_graph")


class ParserArgs(TypedDict, total=False):
    pass


async def run(args: Namespace) -> None:
    start_paper = Paper(
        [AuthorName("root", "root")],
        0,
        "Root",
        "10.1145/3062341.3062363",
        None
    )

    tasks = []
    for traverser in TRAVERSER:
        tasks.append(traverser.collect(start_paper, args.max_depth))

    await gather(*tasks)

    for traverser in TRAVERSER:
        print(traverser.papers)


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
        default=DEFAULT_LOG_LEVEL
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
            "The maximum depth to search papers, if 1, only the root paper is included "
            f"in the result, default is {DEFAULT_MAX_DEPTH}"
        ),
        default=DEFAULT_MAX_DEPTH,
        type=int

    )

    return parser


def init_logging(args: Namespace) -> None:
    if args.log_level < INFO:
        log_format = "[%(asctime)s] %(levelname)s:%(name)s:%(message)s"
    else:
        log_format = "%(levelname)s: %(message)s"

    basicConfig(
        level=args.log_level, format=log_format, datefmt="%Y-%m-%d %H:%M:%S"
    )


def main(**kwargs: Unpack[ParserArgs]) -> None:
    parser = get_arg_parser()
    if len(kwargs) > 0:
        args = Namespace(**kwargs)
    else:
        args = parser.parse_args()

    init_logging(args)

    run_async(run(args))


if __name__ == '__main__':
    main()
