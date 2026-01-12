from json import dumps

from requests import Response, get, post


def get_index_response(
    address: str,
    api_port: str,
    token: str,
    use_ssl: bool,
) -> Response:
    """
    Retrieve the index response given the address, API port and token.

    :param address: The address where request is to be made
    :type address: str

    :param api_port: The API port at the given address
    :type api_port: str

    :param token: The HCI token
    :type token: str

    :param use_ssl: Boolean choice of using SSL
    :type use_ssl: bool

    :return: A response containing information about the index
    :rtype: requests.Response
    """
    url: str = "https://" + address + ":" + api_port + "/api/search/indexes/"
    headers: dict[str, str] = {
        "Accept": "application/json",
        "Authorization": "Bearer " + token,
    }

    response: Response = get(url, headers=headers, verify=use_ssl, timeout=15)

    response.raise_for_status()

    return response


def get_query_response(  # noqa: PLR0913
    query_dict: dict[str, str | list | dict],
    address: str,
    api_port: str,
    token: str,
    use_ssl: bool,
    path_extension: str = "",
) -> Response:
    """
    Retrieve the query response given the address, API port and token.

    :param query_dict: The query dictionary
    :type query_dict: dict[str, str | list | dict]

    :param address: The address where request is to be made
    :type address: str

    :param api_port: The API port at the given address
    :type api_port: str

    :param token: The HCI token
    :type token: str

    :param use_ssl: Boolean choice of using SSL
    :type use_ssl: bool

    :param path_extension:
        Possibly extend the request URL. Used for example when making SQL
        requests. Defaults to ""
    :type path_extension: str, optional

    :return: A response containing information about the query
    :rtype: requests.Response
    """
    if "indexName" not in query_dict:
        msg = "Field indexName is missing in the query dictionary"
        raise RuntimeError(msg)

    url: str = (
        "https://"
        + address
        + ":"
        + api_port
        + "/api/search/query/"
        + path_extension
    )
    query: dict[str, str | list | dict] = query_dict
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": "Bearer " + token,
    }
    response: Response = post(
        url, dumps(query), headers=headers, verify=use_ssl, timeout=15
    )

    response.raise_for_status()

    return response
