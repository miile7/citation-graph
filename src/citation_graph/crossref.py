from configparser import ConfigParser
from logging import getLogger
from typing import Any, Dict, Optional, TypedDict

from citation_graph.restful_database import RestfulDatabase
from citation_graph.static import NAME
from citation_graph.version import get_version


class Credentials(TypedDict, total=False):
    """Crossref credentials as mentioned in
    https://www.crossref.org/documentation/cited-by/retrieve-citations/.

    Attributes:
        email
            The email address for contact, required for politeness
        user
            Either the user name or `<email>/<role>`
        password
            The password
        api_token
            The authorization token for the plus service
    """

    email: str
    user: str
    password: str
    api_token: str


class CrossrefDatabase(RestfulDatabase):
    credentials: Optional[Credentials] = None

    def __init__(self) -> None:
        logger = getLogger("citation_graph.crossref.CrossrefDatabase")
        super().__init__(
            "crossref.org",
            logger,
            paper_api_url="https://api.crossref.org/works/{id}",
            citation_api_url="https://api.crossref.org/works/{id}",
            id_formats={"doi": "{id}"},
            idle_time=5 * 60 / 100,  # 100 requests per five minutes
            use_pagination=False,
        )

    def init_headers(self) -> Dict[str, Any]:
        if self.credentials is None:
            raise Exception("Credentials are not set")

        headers = {
            "User-Agent": (
                f"{NAME} v{get_version()} "
                "(https://github.com/miile7/citation-graph; mailto: miile7@gmx.de)"
            )
            + f", request by mailto:{self.credentials['email']}"
            if "email" in self.credentials
            else ""
        }

        if "api_token" in self.credentials:
            headers["Crossref-Plus-API-Token"] = self.credentials["api_token"]

        return headers

    def load_settings(self, config: ConfigParser) -> None:
        params = {}
        if "email" in config[self.name]:
            params["mailto"] = config[self.name]["email"]
        if "user" in config[self.name] and "password" in config[self.name]:
            params["usr"] = config[self.name]["user"]
            params["pwd"] = config[self.name]["password"]

        self.paper_api_params.update(params)
        self.citation_api_params.update(params)
