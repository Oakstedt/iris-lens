import sys
from collections.abc import Callable
from pathlib import Path
from typing import ParamSpec, TypeVar

from NGPIris.hcp.exceptions import NoBucketMountedError


def create_access_control_policy(user_ID_permissions: dict[str, str]) -> dict:  # noqa: D103
    access_control_policy: dict[str, list] = {
        "Grants": [],
    }
    for user_ID, permission in user_ID_permissions.items():
        if permission not in [
            "FULL_CONTROL",
            "WRITE",
            "WRITE_ACP",
            "READ",
            "READ_ACP",
        ]:
            print("Invalid permission option:", permission)
            sys.exit()
        grantee = {
            "Grantee": {
                "ID": user_ID,
                "Type": "CanonicalUser",
            },
            "Permission": permission,
        }
        access_control_policy["Grants"].append(grantee)
    return access_control_policy


def raise_path_error(path: str) -> None:
    """
    Raise FileNotFoundError if the system path does not exist.

    :param path: Local system path
    :type path: str

    :raises FileNotFoundError: If `path` does not exist
    """
    if not Path(path).exists():
        raise FileNotFoundError('"' + path + '"' + " does not exist")


P = ParamSpec("P")
T = TypeVar("T")


def check_mounted(method: Callable[P, T]) -> Callable[P, T]:
    """
    Decorator for checking if a bucket is mounted. This is meant to be used by
    class methods, hence the possibly odd typing.

    :param method: An arbitrary class method of the `HCPHandler` class
    :type method: Callable[ParamSpec("P"), TypeVar("T")]

    :return: A decorated class method of the `HCPHandler` class
    :rtype: Callable[ParamSpec("P"), TypeVar("T")]
    """

    def check_if_mounted(*args: P.args, **kwargs: P.kwargs) -> T:
        self = args[0]
        if not self.bucket_name: # pyright: ignore[reportAttributeAccessIssue]
            msg = "No bucket is mounted"
            raise NoBucketMountedError(msg)
        return method(*args, **kwargs)

    return check_if_mounted
