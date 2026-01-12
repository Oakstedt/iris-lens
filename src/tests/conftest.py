from collections.abc import Generator
from configparser import ConfigParser
from pathlib import Path
from shutil import rmtree
from typing import Any

from icecream import ic
from pytest import Config, UsageError, fixture

from NGPIris import HCIHandler, HCPHandler

# ruff: noqa: D103, PT013, INP001


class CustomConfig:
    """A typed wrapper around pytest.Config for dynamic attributes."""

    def __init__(self, pytest_config: Config):
        self._config = pytest_config

    @property
    def hcp_h(self) -> HCPHandler:
        """Access the HCPHandler instance."""
        return self._config.hcp_h

    @property
    def hci_h(self) -> HCIHandler:
        """Access the HCIHandler instance."""
        return self._config.hci_h

    def __getattr__(self, name: str) -> Any:
        """Dynamically get attributes set during pytest configuration."""
        return getattr(self._config, name)


def set_section(config: Config, parser: ConfigParser, section: str) -> None:
    parse_dict = dict(parser.items(section))
    for k, v in parse_dict.items():
        setattr(config, k, v)  # Adds attributes dynamically to pytest.Config


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--config",
        action="store",
        default=None,
        help="Path to the configuration file (e.g., path/to/config.ini)",
    )


def pytest_configure(config: Config) -> None:
    config_path = config.getoption("--config")
    if not config_path:
        raise UsageError("--config argument is required.")
    parser = ConfigParser()
    parser.read(str(config_path))

    # Add the INI parser to config
    config.parser = parser

    # Dynamically add an HCPHandler instance to config
    config.hcp_h = HCPHandler(parser.get("General", "credentials_path"))

    # Dynamically add an HCIHandler instance to config
    config.hci_h = HCIHandler(parser.get("General", "credentials_path"))

    # Dynamically add all key-value pairs from "HCP_tests" section
    set_section(config, parser, "HCP_tests")

    # Dynamically add all key-value pairs from "HCI_tests" section
    set_section(config, parser, "HCI_tests")


@fixture(scope="session")
def hcp_result_path(pytestconfig: Config) -> str:
    return pytestconfig.parser.get("HCP_tests", "result_path")  # pyright: ignore[reportAttributeAccessIssue]


@fixture(scope="session")
def hcp_handler(pytestconfig: Config) -> HCPHandler:
    return pytestconfig.hcp_h  # pyright: ignore[reportAttributeAccessIssue]


@fixture(scope="session")
def custom_config_test_bucket(pytestconfig: Config) -> str:
    return pytestconfig.test_bucket  # pyright: ignore[reportAttributeAccessIssue]


@fixture(scope="session", autouse=True)
def clean_up_after_tests(
    hcp_result_path: str,
    hcp_handler: HCPHandler,
    custom_config_test_bucket: str,
) -> Generator[None, Any, None]:
    buckets = hcp_handler.list_buckets()
    bucket_does_not_exist = custom_config_test_bucket not in buckets
    ic("Test bucket:", custom_config_test_bucket)

    # Setup code
    if bucket_does_not_exist:
        hcp_handler.create_bucket(custom_config_test_bucket)

    Path(hcp_result_path).mkdir(exist_ok=True)

    test_folder_path = str(hcp_result_path).rsplit("/", maxsplit=1)[0] + "/"
    Path(hcp_result_path + test_folder_path).mkdir(
        parents=True,
        exist_ok=True,
    )

    yield

    # Teardown code
    if bucket_does_not_exist:  # Will have the same value as in setup code
        hcp_handler.delete_bucket(custom_config_test_bucket)
    if Path(hcp_result_path).exists():
        rmtree(hcp_result_path)


@fixture
def custom_config(pytestconfig: Config) -> CustomConfig:
    """Provide the typed wrapper for pytest.Config."""
    return CustomConfig(pytestconfig)
