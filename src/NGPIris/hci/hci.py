from json import load
from pathlib import Path

from requests import Response, post
from urllib3 import disable_warnings

from NGPIris.hci.helpers import get_index_response, get_query_response
from NGPIris.parse_credentials import CredentialsHandler


class HCIHandler:
    """
    Class for handling HCI requests.
    """

    def __init__(
        self, credentials: str | dict[str, str], use_ssl: bool = False
    ) -> None:
        """
        Class for handling HCI requests.

        :param credentials:
            If `credentials` is a `str`, then it will be interpreted as a path
            to the JSON credentials file. If `credentials` is a `dict`, then a
            dictionary with the appropriate HCI credentials is expected:
            ```
            {
                "username" : "",
                "password" : "",
                "address" : "",
                "auth_port" : "",
                "api_port" : ""
            }
            ```
        :type credentials: str | dict[str, str]

        :param use_ssl: Boolean choice between using SSL, defaults to False
        :type use_ssl: bool, optional
        """
        if type(credentials) is str:
            credentials_handler = CredentialsHandler(credentials)
            self.hci = credentials_handler.hci

            self.username = self.hci["username"]
            self.password = self.hci["password"]
            self.address = self.hci["address"]
            self.auth_port = self.hci["auth_port"]
            self.api_port = self.hci["api_port"]
        elif type(credentials) is dict:
            self.username = credentials["username"]
            self.password = credentials["password"]
            self.address = credentials["address"]
            self.auth_port = credentials["auth_port"]
            self.api_port = credentials["api_port"]

        self.token = ""

        self.use_ssl = use_ssl

        if not self.use_ssl:
            disable_warnings()

    def request_token(self) -> None:
        """
        Request a token from the HCI, which is stored in the HCIHandler object.
        The token is used for every operation that needs to send a request to
        HCI.

        :raises ConnectionError:
            If there was a problem when requesting a token
        """
        url = "https://" + self.address + ":" + self.auth_port + "/auth/oauth/"
        data = {
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
            "scope": "*",
            "client_secret": "hci-client",
            "client_id": "hci-client",
            "realm": "LOCAL",
        }
        try:
            response: Response = post(
                url, data=data, verify=self.use_ssl, timeout=15
            )
        except:  # noqa: E722  # pragma: no cover
            error_msg: str = (
                "The token request made at "
                + url
                + " failed. Please check your connection."
            )
            raise ConnectionError(error_msg) from None

        token: str = response.json()["access_token"]
        self.token = token

    def list_index_names(self) -> list[str]:
        """
        Retrieve a list of all index names.

        :return: A list of index names
        :rtype: list[str]
        """
        response: Response = get_index_response(
            self.address,
            self.api_port,
            self.token,
            self.use_ssl,
        )
        return [entry["name"] for entry in response.json()]

    def look_up_index(self, index_name: str) -> dict:
        """
        Look up index information in the form of a dictionary by submitting
        the index name. Will return an empty dictionary if no index was found.

        :param index_name: The index name
        :type index_name: str

        :return: A dictionary containing information about an index
        :rtype: dict
        """
        response: Response = get_index_response(
            self.address,
            self.api_port,
            self.token,
            self.use_ssl,
        )

        for entry in response.json():
            if entry["name"] == index_name:
                return dict(entry)

        return {}

    def raw_query(self, query_dict: dict[str, str | list | dict]) -> dict:
        """
        Make query to an HCI index, with a dictionary.

        :param query_dict: Dictionary consisting of the query
        :type query_dict: dict[str, str | list | dict]

        :return: Dictionary containing the raw query
        :rtype: dict
        """
        return dict(
            get_query_response(
                query_dict,
                self.address,
                self.api_port,
                self.token,
                self.use_ssl,
            ).json(),
        )

    def raw_query_from_JSON(self, query_path: str) -> dict:
        """
        Make query to an HCI index, with prewritten query in a JSON file.

        :param query_path: Path to the JSON file
        :type query_path: str

        :return: Dictionary containing the raw query
        :rtype: dict
        """
        with Path(query_path).open() as inp:
            return dict(
                get_query_response(
                    dict(load(inp)),
                    self.address,
                    self.api_port,
                    self.token,
                    self.use_ssl,
                ).json(),
            )

    def query(
        self,
        index_name: str,
        query_string: str = "",
        facets: list[str] = [],  # noqa: B006
    ) -> dict:
        """
        Make a query to the HCI based on the parameters of this method.

        :param index_name: Name of the index
        :type index_name: str

        :param query_string: The Solr query string. Defaults to the empty string
        :type query_string: str, optional

        :param facets:
            List of facets that should be returned included in the response.
            Defaults to []
        :type facets: list[str], optional

        :return: The response in the form of a dictionary
        :rtype: dict
        """
        facetRequests = [{"fieldName": facet} for facet in facets]
        return self.raw_query(
            {
                "indexName": index_name,
                "queryString": query_string,
                "facetRequests": facetRequests,
            },
        )
