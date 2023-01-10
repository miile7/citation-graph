from logging import Logger
from requests import get
from typing import (
    Any,
    Dict,
    Generic,
    List,
    Optional,
    Tuple,
    TypeVar,
    TypedDict,
    Union,
    cast,
)

from citation_graph.database import REQUEST_TIMEOUT, CitationCache, Database, PaperCache
from citation_graph.paper import IdType, Paper

PT = TypeVar("PT", Dict[str, Any], TypedDict)  # paper result type

CT = TypeVar("CT", Dict[str, Any], TypedDict)  # citations result type


class RestfulDatabase(Database, Generic[PT, CT]):
    paper_api_url: str
    citation_api_url: str
    id_formats: Dict[IdType, str]
    api_params: Dict[str, Any]
    paper_api_params: Dict[str, Any]
    citation_api_params: Dict[str, Any]
    pagination_params: Tuple[str, str]
    _headers: Dict[str, Any] = {}

    def __init__(
        self,
        name: str,
        logger: Logger,
        paper_api_url: str,
        citation_api_url: str,
        id_formats: Dict[IdType, str],
        idle_time: float,
        use_pagination: bool,
        page_size: int = 100,
        error_count: int = 10,
        api_params: Dict[str, Any] = {},
        paper_api_params: Dict[str, Any] = {},
        citation_api_params: Dict[str, Any] = {},
        pagination_params: Tuple[str, str] = ("offset", "limit"),
        citation_cache: Optional[CitationCache] = None,
        paper_cache: Optional[PaperCache] = None,
    ) -> None:
        super().__init__(
            name,
            logger,
            idle_time,
            use_pagination,
            page_size,
            error_count,
            citation_cache,
            paper_cache,
        )

        self.paper_api_url = paper_api_url
        self.citation_api_url = citation_api_url
        self.id_formats = id_formats
        self.api_params = api_params
        self.paper_api_params = paper_api_params
        self.citation_api_params = citation_api_params
        self.pagination_params = pagination_params

    def init_headers(self) -> Dict[str, Any]:
        return {}

    def get_headers(self) -> Dict[str, Any]:
        if len(self._headers) == 0:
            self._headers = self.init_headers()

        return self._headers

    def get_paper_id_for_url(
        self, paper: Union[Paper, Tuple[IdType, Union[str, int, None]]]
    ) -> str:
        id: Union[str, int, None]
        id_type: Optional[IdType]

        if isinstance(paper, tuple):
            id_type, id = paper
        else:
            id_type = paper.get_id_type()
            id = paper.get_raw_id()

        if id is None or id_type is None:
            raise KeyError("Ids of type None are invalid")

        for compare_id_type, id_format in self.id_formats.items():
            if id_type == compare_id_type:
                return id_format.format(id=id)

        raise KeyError(
            "Cannot find an identifier that is supported by the current database."
        )

    def get_paper_url(
        self, paper: Union[Paper, Tuple[IdType, Union[str, int, None]]]
    ) -> str:
        return self.paper_api_url.format(id=self.get_paper_id_for_url(paper))

    def get_citing_papers_url(
        self, paper: Union[Paper, Tuple[IdType, Union[str, int, None]]]
    ) -> str:
        return self.citation_api_url.format(id=self.get_paper_id_for_url(paper))

    def _get(self, url: Union[str, bytes], params: Dict[Any, Any]) -> Any:
        headers = self.get_headers()

        self.logger.debug(
            "Executing GET request on "
            f"{url}?{'&'.join(f'{n}={v}' for n, v in params.items())} "
            f"with headers {', '.join(f'{n}={v}' for n, v in headers.items())}"
        )

        return get(url, params, timeout=REQUEST_TIMEOUT, headers=headers)

    async def _get_paper(self, id_type: IdType, id: Union[str, int]) -> Paper:
        url = self.get_paper_url((id_type, id))
        self.logger.info(f"Fetching paper for {id_type} {id} by url {url}")

        params = self.paper_api_params.copy()
        params.update(self.api_params)

        result = self._get(url, params)
        r = result.json()

        if not isinstance(r, dict):
            raise ValueError(f"Could not find information for paper with id {id}")

        return self._parse_json_result_paper(cast(PT, r))

    def _parse_json_result_paper(self, json_result: PT) -> Paper:
        raise NotImplementedError()

    async def _get_cited_by(self, paper: Paper, offset: int, limit: int) -> List[Paper]:
        try:
            url = self.get_citing_papers_url(paper)
        except KeyError:
            self.logger.info(
                f"Skipping {paper}, cannot find an identifier for database requests"
            )
            return []

        params: Dict[str, Any] = self.citation_api_params.copy()
        params[self.pagination_params[0]] = offset
        # load more for caching, this is the same request and does not have any
        # penalty from the database concerning requests
        params[self.pagination_params[1]] = max(limit, self.page_size)
        params.update(self.api_params)

        self.logger.info(
            f"Fetching results ({offset}..{offset + limit}) for {paper} from {url} "
        )
        self.logger.debug(
            f"Actually loading {params[self.pagination_params[1]]} results for improved"
            " caching, there is no limit for items, only for requests, therefore try to"
            " get as much as possible"
        )
        result = self._get(url, params)

        r = result.json()
        if (
            not isinstance(r, dict)
            or "data" not in r
            or not isinstance(r["data"], list)
        ):
            raise ValueError(f"Cannot parser the returned json data: \n\n{result.text}")

        self.logger.debug(f"Parsing result of {paper}")

        cited_by_papers = self._parse_json_result_citing_paper(cast(CT, r))

        self.logger.debug(f"Found {len(cited_by_papers)} citations of {paper}")

        if len(cited_by_papers) > limit:
            self.logger.debug(
                f"Caching last {len(cited_by_papers) - limit} elements for later use, "
                f"returning only the first {limit} elements as requested."
            )
            cache_only = cited_by_papers[limit:]
            self.cache_citations(paper, cache_only, offset, limit)

            cited_by_papers = cited_by_papers[:limit]

        return cited_by_papers

    def _parse_json_result_citing_paper(self, result: CT) -> List[Paper]:
        raise NotImplementedError()
