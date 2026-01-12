from NGPIris import HCPHandler
from NGPIris.hcp.helpers import check_mounted


class HCPStatistics(HCPHandler):
    """
    Class for handling HCP statistics requests. Subclass of `HCPHandler`.
    """

    def __init__(
        self,
        credentials_path: str,
        use_ssl: bool = False,
        custom_config_path: str = "",
    ) -> None:
        """
        Constructor for the `HCPStatistics` class. Identical to the constructor
        of `HCPHandler`.
        """
        super().__init__(credentials_path, use_ssl, custom_config_path)

    @check_mounted
    def get_namespace_settings(self) -> dict:
        """
        Get namespace/bucket settings.

        :return: Namespace/bucket settings as a dictionary.
        :rtype: dict
        """
        return self.get_response("/namespaces/" + self.bucket_name) #pyright: ignore[reportOperatorIssue]

    @check_mounted
    def get_namespace_statistics(self) -> dict:
        """
        Get namespace/bucket statistics.

        :return: Namespace/bucket statistics as a dictionary.
        :rtype: dict
        """
        return self.get_response(
            "/namespaces/" + self.bucket_name + "/statistics", #pyright: ignore[reportOperatorIssue]
        )

    @check_mounted
    def get_namespace_permissions(self) -> dict:
        """
        Get namespace/bucket permissions.

        :return: Namespace/bucket permissions as a dictionary.
        :rtype: dict
        """
        return self.get_response(
            "/namespaces/" + self.bucket_name + "/permissions", #pyright: ignore[reportOperatorIssue]
        )
