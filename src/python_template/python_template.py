from argparse import ArgumentParser, Namespace
from logging import DEBUG, INFO, WARNING, basicConfig, getLogger
from typing import TypedDict
from typing_extensions import Unpack

from python_template.version import get_version


NAME = "python_template"

DEFAULT_LOG_LEVEL = WARNING


logger = getLogger(NAME)


class ParserArgs(TypedDict, total=False):
    pass


def run(args: Namespace) -> None:
    pass


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

    run(args)


if __name__ == '__main__':
    main()
