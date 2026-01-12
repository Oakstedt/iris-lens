from json import load
from pathlib import Path
from typing import TypeAlias

Credentials: TypeAlias = dict[str, dict[str, str]]


class CredentialsHandler:
    """
    Class for handling credentials parsing.
    """

    def __init__(self, credentials_path: str) -> None:
        """
        Class for handling credentials to HCP and HCI.

        :param credentials_path: Path to the credentials JSON file
        :type credentials_path: str
        """
        self.hcp: dict[str, str] = {}
        self.hci: dict[str, str] = {}

        credentials: Credentials = parse_credentials(credentials_path)
        for key, value in credentials.items():
            setattr(self, key, value)


def all_fields_empty(key: str, credentials: Credentials) -> bool:
    """
    Predicate that checks if all fields in `credentials` with a given `key` are
    empty.

    :param key: Key for to be accessed in `credentials`
    :type key: str

    :param credentials: The credentials
    :type credentials: Credentials
    """
    return all(v == "" for v in credentials[key].values())


def check_empty_field(credentials: Credentials) -> None:
    """
    Makes the following checks:
     - All fields in the credentials file are empty
     - If fields under `hcp` and `hci` are only partially filled in
    If any of the above are true, then `RuntimeError` is raised

    :param credentials: Credentials to be checked
    :type credentials: Credentials

    :raise RuntimeError: If any check is true
    """  # noqa: D400, D415
    if all(all_fields_empty(k, credentials) for k in credentials):
        msg = (
            "Missing entries in all fields in the credentials file. "
            "Please enter your credentials in the credentials file"
        )
        raise RuntimeError(msg)
    empty_fields_per_entry: dict[str, list[str]] = {}
    for k1, d in credentials.items():
        # If all fields in *either* hci or hcp is empty then continue
        if all_fields_empty(k1, credentials):
            continue
        empty_fields: list[str] = []
        for k2, v in d.items():
            if v == "":
                empty_fields.append("\t- " + k2 + "\n")
        if empty_fields:
            empty_fields_per_entry[k1] = empty_fields

    all_empty_fields = []
    for entry, fields in empty_fields_per_entry.items():
        fields.insert(0, "- " + entry + ":\n")
        all_empty_fields.append("".join(fields))

    if all_empty_fields:
        msg = (
            "Missing fields for the following entries in the credentials"
            " file:\n" + "".join(all_empty_fields)
        )
        raise RuntimeError(msg)


def parse_credentials(credentials_path: str) -> Credentials:
    """
    Parse credentials at the given `credentials_path`.

    :param credentials_path: Path to credentials
    :type credentials_path: str

    :return: Parsed credentials
    :rtype: Credentials = dict[str, dict[str, str]]
    """
    with Path(credentials_path).open() as inp:
        credentials: Credentials = load(inp)
        check_empty_field(credentials)
        return credentials
