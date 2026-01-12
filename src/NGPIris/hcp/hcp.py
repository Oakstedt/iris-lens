import re
from collections.abc import Generator
from configparser import ConfigParser
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from bitmath import Byte, TiB
from bitmath import parse_string as bitmath_parse
from boto3 import client
from boto3.s3.transfer import TransferConfig
from botocore.client import Config
from botocore.exceptions import ClientError, EndpointConnectionError
from more_itertools import peekable
from parse import Result, parse
from rapidfuzz import fuzz, process, utils
from requests import get
from requests.exceptions import HTTPError
from tqdm import tqdm
from urllib3 import disable_warnings

from NGPIris.hcp.exceptions import (
    BucketForbiddenError,
    BucketNotFoundError,
    DownloadLimitReachedError,
    IsFolderObjectError,
    NoBucketMountedError,
    NotAValidTenantError,
    NotFoundError,
    NotSufficientPermissionsError,
    ObjectAlreadyExistError,
    ObjectDoesNotExistError,
    SubfolderError,
    UnableToParseEndpointError,
    UnallowedCharacterError,
)
from NGPIris.hcp.helpers import (
    check_mounted,
    create_access_control_policy,
    raise_path_error,
)
from NGPIris.parse_credentials import CredentialsHandler

if TYPE_CHECKING:
    from botocore.paginate import PageIterator, Paginator

_KB = 1024
_MB = _KB * _KB


class HCPHandler:
    """
    Class for handling HCP requests.
    """

    def __init__(
        self,
        credentials: str | dict[str, str],
        use_ssl: bool = False,
        custom_config_path: str = "",
    ) -> None:
        """
        Constructor for the `HCPHandler` class.

        :param credentials:
            If `credentials` is a `str`, then it will be interpreted as a path
            to the JSON credentials file. If `credentials` is a `dict`, then a
            dictionary with the appropriate HCP credentials is expected:
            ```
            {
                "endpoint" : "",
                "username" : "",
                "password" : ""
            }
            ```
        :type credentials: str | dict[str, str]

        :param use_ssl: Boolean choice between using SSL, defaults to False
        :type use_ssl: bool, optional

        :param custom_config_path:
            Path to a .ini file for customs settings regarding download and
            upload
        :type custom_config_path: str, optional

        :raise NotAValidTenantError:
            If the tenant in the specified endpoint is not valid

        :raise UnableToParseEndpointError: The endpoint could not be parsed
        """
        # Determine type of `credentials`
        if type(credentials) is str:
            parsed_credentials = CredentialsHandler(credentials).hcp

            self.endpoint = "https://" + parsed_credentials["endpoint"]
            self.username = (
                parsed_credentials["username"]
                if parsed_credentials.get("username")
                else parsed_credentials["aws_access_key_id"]
            )
            self.password = (
                parsed_credentials["password"]
                if parsed_credentials.get("password")
                else parsed_credentials["aws_secret_access_key"]
            )
        elif type(credentials) is dict:
            self.endpoint = "https://" + credentials["endpoint"]
            self.username = (
                credentials["username"]
                if credentials.get("username")
                else credentials["aws_access_key_id"]
            )
            self.password = (
                credentials["password"]
                if credentials.get("password")
                else credentials["aws_secret_access_key"]
            )

        # A lookup table for GMC names to HCP tenant names
        gmc_tenant_map = {
            "gmc-joint": "vgtn0008",
            "gmc-west": "vgtn0012",
            "gmc-southeast": "vgtn0014",
            "gmc-south": "vgtn0015",
            "gmc-orebro": "vgtn0016",
            "gmc-karolinska": "vgtn0017",
            "gmc-north": "vgtn0018",
            "gmc-uppsala": "vgtn0019",
        }

        self.tenant = None
        for endpoint_format_string in [
            "https://{}.ngp-fs1000.vgregion.se",
            "https://{}.ngp-fs2000.vgregion.se",
            "https://{}.ngp-fs3000.vgregion.se",
            "https://{}.hcp1.vgregion.se",
            "https://{}.vgregion.sjunet.org",
        ]:
            tenant_parse = parse(endpoint_format_string, self.endpoint)
            if type(tenant_parse) is Result:
                tenant = str(tenant_parse[0])
                if (
                    endpoint_format_string == "https://{}.vgregion.sjunet.org"
                ):  # Check if endpoint is Sjunet
                    mapped_tenant = gmc_tenant_map.get(tenant)
                    if mapped_tenant:
                        self.tenant = mapped_tenant
                    else:
                        raise NotAValidTenantError(
                            'The provided tenant name, "'
                            + tenant
                            + '", is not a valid tenant name. Hint: did you'
                            + "spell it correctly?",
                        )
                else:
                    self.tenant = tenant

                break

        if not self.tenant:
            raise UnableToParseEndpointError(
                'Unable to parse endpoint, "'
                + self.endpoint
                + '". Make sure that you have entered the correct endpoint in'
                + "your credentials JSON file. "
                + 'Hints:\n - The endpoint should *not* contain "https://" or'
                + "port numbers\n - Is the endpoint spelled correctly?",
            )
        self.base_request_url = (
            self.endpoint + ":9090/mapi/tenants/" + self.tenant
        )
        self.token = self.username + ":" + self.password
        self.bucket_name = None
        self.use_ssl = use_ssl

        if not self.use_ssl:
            disable_warnings()

        s3_config = Config(
            s3={
                "addressing_style": "path",
                "payload_signing_enabled": True,
            },
            signature_version="s3v4",
        )

        self.s3_client = client(
            "s3",
            aws_access_key_id=self.username,
            aws_secret_access_key=self.password,
            endpoint_url=self.endpoint,
            verify=self.use_ssl,
            config=s3_config,
        )

        if custom_config_path:  # pragma: no cover
            ini_config = ConfigParser()
            ini_config.read(custom_config_path)

            self.transfer_config = TransferConfig(
                multipart_threshold=ini_config.getint(
                    "hcp",
                    "multipart_threshold",
                ),
                max_concurrency=ini_config.getint("hcp", "max_concurrency"),
                multipart_chunksize=ini_config.getint(
                    "hcp",
                    "multipart_chunksize",
                ),
                use_threads=ini_config.getboolean("hcp", "use_threads"),
            )
        else:
            self.transfer_config = TransferConfig(
                multipart_threshold=10 * _MB,
                max_concurrency=30,
                multipart_chunksize=40 * _MB,
                use_threads=True,
            )

    def get_MAPI_request(self, path_extension: str = "") -> dict:
        """
        Make a GET request to the HCP in order to use the builtin MAPI.

        :param path_extension:
            Extension for the base request URL, defaults to the empty string
        :type path_extension: str, optional

        :return: The response as a dictionary
        :rtype: dict
        """
        url = self.base_request_url + path_extension
        headers = {
            "Authorization": "HCP " + self.token,
            "Cookie": "hcp-ns-auth=" + self.token,
            "Accept": "application/json",
        }
        response = get(
            url,
            headers=headers,
            verify=self.use_ssl,
            timeout=60,
        )

        try:
            response.raise_for_status()
        except HTTPError as http_e:
            if response.status_code == 403:  # noqa: PLR2004
                msg = (
                    "You lack the sufficient permissions needed for your "
                    "request"
                )
                raise NotSufficientPermissionsError(msg) from http_e
            if response.status_code == 404:  # noqa: PLR2004
                msg = "The request URL " + str(url) + " could not be found"
                raise NotFoundError(msg) from http_e
            raise

        return dict(response.json())

    # ---------------------------- User methods ----------------------------

    def get_users(self) -> list[str]:
        """
        Get a list of users on the tenant.

        :return: List of users on the tenant
        :rtype: list[str]
        """
        return self.get_MAPI_request("/userAccounts").get("username", [])

    def get_user_roles(self, username: str) -> list[str]:
        """
        Get the user roles for a given user on the tenant.

        :param username: A username on the tenant
        :type username: str

        :return: List of roles the user has
        :rtype: list[str]
        """
        return (
            self.get_MAPI_request("/userAccounts/" + username)
            .get("roles", {})
            .get("role")
        )  # pytype: disable=bad-return-type

    def is_user_admin(self, username: str) -> bool:
        """
        Predicate for checking if a given user has the admin role.

        :param username: The user name
        :type username: str

        :rtype: bool
        """
        return "ADMINISTRATOR" in self.get_user_roles(username)

    # ---------------------------- Util methods ----------------------------

    def test_connection(self, bucket_name: str = "") -> dict:
        """
        Test the connection to the mounted bucket or another bucket which is
        supplied as the argument :py:obj:`bucket_name`.

        :param bucket_name:
            The name of the bucket to be mounted. Defaults to the empty string
        :type bucket_name: str, optional

        :raises NoBucketMountedError: If no bucket is selected
        :raises EndpointConnectionError: If the endpoint can't be reached
        :raises BucketNotFoundError: If no bucket of that name was found
        :raises Exception: Other exceptions

        :return: A dictionary of the response
        :rtype: dict
        """
        if not bucket_name and self.bucket_name:
            bucket_name = self.bucket_name
        elif bucket_name:
            pass
        else:
            msg = (
                "No bucket selected. Either use `mount_bucket` first or "
                "supply the optional `bucket_name` parameter for "
                "`test_connection`"
            )
            raise NoBucketMountedError(msg)

        response = {}
        try:
            response = dict(self.s3_client.head_bucket(Bucket=bucket_name))
        except EndpointConnectionError:  # pragma: no cover
            raise
        except ClientError as e:
            status_code = e.response["ResponseMetadata"].get(
                "HTTPStatusCode",
                -1,
            )
            match status_code:
                case 404:
                    raise BucketNotFoundError(
                        'Bucket "' + bucket_name + '" was not found',
                    ) from e
                case 403:
                    raise BucketForbiddenError(
                        'Bucket "'
                        + bucket_name
                        + '" could not be accessed due to lack of permissions',
                    ) from e
        except Exception:  # pragma: no cover
            raise

        return response

    # ---------------------------- Bucket methods ----------------------------

    def mount_bucket(self, bucket_name: str) -> None:
        """
        Mount bucket that is to be used. This method needs to executed in order
        for most of the other methods to work. It mainly concerns operations
        with download and upload.

        :param bucket_name: The name of the bucket to be mounted
        :type bucket_name: str
        """
        # Check if bucket exist
        self.test_connection(bucket_name=bucket_name)
        self.bucket_name = bucket_name

    def create_bucket(self, bucket_name: str) -> None:
        """
        Create a bucket. The user in the given credentials will be the owner of
        the bucket.

        :param bucket_name: Name of the new bucket
        :type bucket_name: str
        """
        self.s3_client.create_bucket(
            Bucket=bucket_name,
        )

    def delete_bucket(self, bucket: str) -> None:
        """
        Delete a specified bucket.

        :param bucket: The bucket to be deleted
        :type bucket: str
        """
        # If the deletion was not successful, `self.s3_client.delete_bucket`
        # would have thrown an error
        self.s3_client.delete_bucket(
            Bucket=bucket,
        )

    class ListBucketsOutputMode(Enum):
        FULL = "full"
        EXTENDED = "extended"
        SIMPLE = "simple"
        MINIMAL = "minimal"
        BUCKET_ONLY = "bucket_only"

    def list_buckets(
        self,
        output_mode: ListBucketsOutputMode = ListBucketsOutputMode.EXTENDED,
    ) -> list[dict[str, Any]]:
        """
        List all available buckets at endpoint along with statistics for each
        bucket.

        :return: A list of buckets and their statistics
        :rtype: list[dict[str, Any]]
        """
        response = self.get_MAPI_request("/namespaces")
        buckets: list[str] = response["name"]
        output_list = []
        for bucket in buckets:
            stats = self.get_MAPI_request(
                "/namespaces/" + bucket + "/statistics"
            )
            bucket_information = self.get_MAPI_request("/namespaces/" + bucket)

            base = {"Bucket": bucket}

            # Turn headers from camelCase to human readable text
            stats = {
                re.sub(r"(?<=[a-z])([A-Z])", r" \1", k).capitalize(): _
                for k, _ in stats.items()
            }
            bucket_information = {
                re.sub(r"(?<=[a-z])([A-Z])", r" \1", k).capitalize(): _
                for k, _ in bucket_information.items()
            }

            # Parse `"Hard quota"` value to be just a number
            bucket_information["Hard quota (Bytes)"] = int(
                bitmath_parse(
                    # TODO(EB): `"Hard quota"` is written as being decimal
                    # (MB, GB, TB, etc), but it is probably binary
                    # (MiB, GiB, TiB, etc). As such the `bitmath_parse` will not
                    # be 100% correct, and should be corrected soon, but that is
                    # annoying so I won't right now :/
                    bucket_information["Hard quota"]
                ).to_Byte()
            )

            bucket_information["Soft quota (%)"] = bucket_information[
                "Soft quota"
            ]
            del bucket_information["Soft quota"]

            for col in ["Ingested volume", "Storage capacity used"]:
                stats[col + " (Bytes)"] = stats[col]
                del stats[col]

            match output_mode:
                case HCPHandler.ListBucketsOutputMode.FULL:
                    output_list.append(base | stats | bucket_information)

                case HCPHandler.ListBucketsOutputMode.EXTENDED:
                    bi_fields = [
                        "Hard quota (Bytes)",
                        "Soft quota (%)",
                        "Description",
                        "Owner",
                    ]
                    output_list.append(
                        base
                        | stats
                        | {f: bucket_information[f] for f in bi_fields}
                    )

                case HCPHandler.ListBucketsOutputMode.SIMPLE:
                    stats_fields = [
                        "Ingested volume (Bytes)",
                        "Storage capacity used (Bytes)",
                        "Object count",
                    ]
                    bi_fields = [
                        "Hard quota (Bytes)",
                        "Soft quota (%)",
                        "Owner",
                    ]

                    output_list.append(
                        base
                        | {f: stats[f] for f in stats_fields}
                        | {f: bucket_information[f] for f in bi_fields}
                    )

                case HCPHandler.ListBucketsOutputMode.MINIMAL:
                    stats_fields = ["Object count"]
                    bi_fields = [
                        "Hard quota (Bytes)",
                        "Soft quota (%)",
                        "Owner",
                    ]

                    output_list.append(
                        base
                        | {f: stats[f] for f in stats_fields}
                        | {f: bucket_information[f] for f in bi_fields}
                    )

                case HCPHandler.ListBucketsOutputMode.BUCKET_ONLY:
                    output_list.append(base)
        return output_list

    # ---------------------------- Object methods ----------------------------

    class ListObjectsOutputMode(Enum):
        SIMPLE = "simple"
        EXTENDED = "extended"
        MINIMAL = "minimal"

    @check_mounted
    def list_objects(  # noqa: C901
        self,
        path_key: str = "",
        output_mode: ListObjectsOutputMode = ListObjectsOutputMode.EXTENDED,
        files_only: bool = False,
    ) -> Generator[dict[str, Any], Any, None]:
        r"""
        List all objects in the mounted bucket as a generator.
        If one wishes to get the result as a list, use :py:function:`list` to
        type cast the generator

        :param path_key:
            Filter string for which keys to list, specifically for finding
            objects in certain folders. Defaults to \"the root\" of the bucket
        :type path_key: str, optional

        :param output_mode:
            The upload mode of the transfer is any of the following:\n
                    HCPHandler.ListObjectsOutputMode.SIMPLE,\n
                    HCPHandler.ListObjectsOutputMode.EXTENDED,\n
                    HCPHandler.ListObjectsOutputMode.MINIMAL\n
            Default is EXTENDED
        :type output_mode: ListObjectsOutputMode, optional

        :param files_only: If True, only yield file objects. Defaults to False
        :type files_only: bool, optional

        :yield: A generator of all objects in specified folder in a bucket
        :rtype: Generator
        """  # noqa: D400, D415

        def _format_output_dictionary(
            key: str,
            object_metadata: dict,
            is_file: bool,
            output_mode: HCPHandler.ListObjectsOutputMode,
        ) -> dict[str, Any]:
            base = {
                "Key": key,
                "IsFile": is_file,
            }

            match output_mode:
                case HCPHandler.ListObjectsOutputMode.MINIMAL:
                    return base

                case HCPHandler.ListObjectsOutputMode.SIMPLE:
                    return base | {
                        "LastModified": object_metadata["LastModified"],
                        "Size": object_metadata.get("Size", ""),
                    }

                case HCPHandler.ListObjectsOutputMode.EXTENDED:
                    return base | {
                        "LastModified": object_metadata["LastModified"],
                        "Size": object_metadata.get("Size", ""),
                        "ETag": object_metadata["ETag"],
                    }

        paginator: Paginator = self.s3_client.get_paginator("list_objects_v2")
        pages: PageIterator = paginator.paginate(
            Bucket=self.bucket_name,
            Prefix=path_key,
            Delimiter="/",
        )

        for page in pages:
            page: dict | None
            # Check if `page` is None
            if not page:
                # Defensive: paginator shouldn't normally yield falsy pages
                continue

            if not files_only:
                # Hide folder objects when flag `files_only` is True
                # Handle folder objects before file objects
                for folder_object in page.get("CommonPrefixes", []):
                    folder_object: dict
                    key = folder_object["Prefix"]
                    folder_object_metadata = self.get_object(
                        key,
                    )
                    yield _format_output_dictionary(
                        key, folder_object_metadata, False, output_mode
                    )

            # Handle file objects
            for file_object_metadata in page.get("Contents", []):
                file_object_metadata: dict
                key = file_object_metadata["Key"]
                if key != path_key:
                    yield _format_output_dictionary(
                        key, file_object_metadata, True, output_mode
                    )

    @check_mounted
    def get_object(self, key: str) -> dict:
        """
        Retrieve object metadata.

        :param key: The object name
        :type key: str

        :return: A dictionary containing the object metadata
        :rtype: dict
        """
        return dict(
            self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=key,
            ),
        )

    @check_mounted
    def object_exists(self, key: str) -> bool:
        """
        Check if a given object is in the mounted bucket.

        :param key: The object name
        :type key: str

        :return: True if the object exist, otherwise False
        :rtype: bool
        """
        try:
            response = self.get_object(key)
            return response["ResponseMetadata"]["HTTPStatusCode"] == 200  # noqa: PLR2004
        except Exception:  # noqa: BLE001  # pragma: no cover
            return False

    @check_mounted
    def download_file(
        self,
        key: str,
        local_file_path: str,
        show_progress_bar: bool = True,
    ) -> None:
        """
        Download one object file from the mounted bucket.

        :param key: Name of the object
        :type key: str

        :param local_file_path:
            Path to a file on your local system where the contents of the
            object file can be put
        :type local_file_path: str

        :param show_progress_bar:
            Boolean choice of displaying a progress bar. Defaults to True
        :type show_progress_bar: bool, optional

        :raises ObjectDoesNotExistError:
            If the object does not exist in the bucket

        :raises ClientError:
            Underlying botocore exception.
            https://boto3.amazonaws.com/v1/documentation/api/latest/guide/error-handling.html#aws-service-exceptions
        :raises Exception: Other exceptions
        """
        try:
            self.get_object(key)
        except:  # noqa: E722
            msg = (
                'Could not find object "'
                + key
                + '" in bucket "'
                + str(self.bucket_name)
                + '"'
            )
            raise ObjectDoesNotExistError(
                msg,
            ) from None

        if show_progress_bar:
            file_size: int = self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=key,
            )["ContentLength"]
            with tqdm(
                total=file_size,
                unit="B",
                unit_scale=True,
                desc=key,
            ) as pbar:
                self.s3_client.download_file(
                    Bucket=self.bucket_name,
                    Key=key,
                    Filename=local_file_path,
                    Config=self.transfer_config,
                    Callback=lambda bytes_transferred: pbar.update(
                        bytes_transferred,
                    ),
                )
        else:
            self.s3_client.download_file(
                Bucket=self.bucket_name,
                Key=key,
                Filename=local_file_path,
                Config=self.transfer_config,
            )

    @check_mounted
    def download_folder(
        self,
        folder_key: str,
        local_folder_path: str,
        use_download_limit: bool = False,
        download_limit_in_bytes: Byte = TiB(1).to_Byte(),  # noqa: B008
        show_progress_bar: bool = True,
    ) -> None:
        """
        Download multiple objects from a folder in the mounted bucket.

        :param folder_key: Name of the folder
        :type folder_key: str

        :param local_folder_path:
            Path to a folder on your local system where the contents of the
            objects can be put
        :type local_folder_path: str

        :param use_download_limit:
            Boolean choice for using a download limit. Defaults to False
        :type use_download_limit: bool, optional

        :param download_limit_in_bytes:
            The optional download limit in Byte (from the package `bitmath`).
            Defaults to 1 TB (`TiB(1).to_Byte()`)
        :type download_limit_in_bytes: Byte, optional

        :param show_progress_bar:
            Boolean choice of displaying a progress bar. Defaults to True
        :type show_progress_bar: bool, optional

        :raises ObjectDoesNotExistError:
            If the object does not exist in the bucket

        :raises DownloadLimitReachedError:
            If download limit was reached while downloading files

        :raises NotADirectoryError: If local_folder_path is not a directory
        """
        try:
            self.get_object(folder_key)
        except:  # noqa: E722
            msg = (
                'Could not find object "'
                + folder_key
                + '" in bucket "'
                + str(self.bucket_name)
                + '"'
            )
            raise ObjectDoesNotExistError(
                msg,
            ) from None
        if Path(local_folder_path).is_dir():
            current_download_size_in_bytes = Byte(
                0,
            )  # For tracking download limit
            (Path(local_folder_path) / Path(folder_key)).mkdir(
                parents=True,
            )  # Create "base folder"
            for hcp_object in self.list_objects(
                folder_key,
            ):  # Build the tree with directories or add files:
                p = Path(local_folder_path) / Path(hcp_object["Key"])
                if not hcp_object["IsFile"]:  # If the object is a "folder"
                    p.mkdir(parents=True)
                    self.download_folder(
                        folder_key=str(hcp_object["Key"]),
                        local_folder_path=local_folder_path,
                        use_download_limit=use_download_limit,
                        show_progress_bar=show_progress_bar,
                        download_limit_in_bytes=download_limit_in_bytes
                        - current_download_size_in_bytes,
                    )
                else:  # If the object is a file
                    current_download_size_in_bytes += Byte(hcp_object["Size"])
                    if (
                        current_download_size_in_bytes
                        >= download_limit_in_bytes
                        and use_download_limit
                    ):
                        msg = (
                            "The download limit was reached when downloading"
                            " files"
                        )
                        raise DownloadLimitReachedError(msg)
                    self.download_file(
                        hcp_object["Key"],
                        p.as_posix(),
                        show_progress_bar=show_progress_bar,
                    )
        else:
            raise NotADirectoryError(
                local_folder_path + " is not a directory",
            )

    class UploadMode(Enum):
        STANDARD = "standard"
        SIMPLE = "simple"
        EQUAL_PARTS = "equal_parts"

    @check_mounted
    def upload_file(
        self,
        local_file_path: str,
        key: str = "",
        show_progress_bar: bool = True,
        upload_mode: UploadMode = UploadMode.STANDARD,
        equal_parts: int = 5,
    ) -> None:
        r"""
        Upload one file to the mounted bucket.

        :param local_file_path: Path to the file to be uploaded
        :type local_file_path: str

        :param key:
            An optional new name for the file object on the bucket.
            Defaults to the same name as the file
        :type key: str, optional

        :param show_progress_bar:
            Boolean choice of displaying a progress bar. Defaults to True
        :type show_progress_bar: bool, optional

        :param upload_mode:
            The upload mode of the transfer is any of the following:\n
                HCPHandler.UploadMode.STANDARD,\n
                HCPHandler.UploadMode.SIMPLE,\n
                HCPHandler.UploadMode.EQUAL_PARTS\n
            Default is STANDARD
        :type upload_mode: UploadMode, optional

        :param equal_parts:
            The number of equal parts that each file should be divided into when
            using the HCPHandler.UploadMode.EQUAL_PARTS mode. Default is 5
        :type equal_parts: int, optional

        :raises FileNotFoundError: If `path` does not exist

        :raises UnallowedCharacterError: If the \"\\\" is used in the file path

        :raises ObjectAlreadyExistError:
            If the object already exist on the mounted bucket
        """
        raise_path_error(local_file_path)

        if not key:
            file_name = Path(local_file_path).name
            key = file_name

        if "\\" in local_file_path:
            msg = 'The "\\" character is not allowed in the file path'
            raise UnallowedCharacterError(msg)

        if self.object_exists(key):
            msg = 'The object "' + key + '" already exist in the mounted bucket'
            raise ObjectAlreadyExistError(msg)

        file_size: int = Path(local_file_path).stat().st_size

        match upload_mode:
            case HCPHandler.UploadMode.STANDARD:
                config = self.transfer_config
            case HCPHandler.UploadMode.SIMPLE:
                config = TransferConfig(multipart_chunksize=file_size)
            case HCPHandler.UploadMode.EQUAL_PARTS:
                config = TransferConfig(
                    multipart_chunksize=round(file_size / equal_parts),
                )

        if show_progress_bar:
            with tqdm(
                total=file_size,
                unit="B",
                unit_scale=True,
                desc=local_file_path,
            ) as pbar:
                self.s3_client.upload_file(
                    Filename=local_file_path,
                    Bucket=self.bucket_name,
                    Key=key,
                    Config=config,
                    Callback=lambda bytes_transferred: pbar.update(
                        bytes_transferred,
                    ),
                )
        else:
            self.s3_client.upload_file(
                Filename=local_file_path,
                Bucket=self.bucket_name,
                Key=key,
                Config=config,
            )

    @check_mounted
    def upload_folder(
        self,
        local_folder_path: str,
        key: str = "",
        show_progress_bar: bool = True,
        upload_mode: UploadMode = UploadMode.STANDARD,
        equal_parts: int = 5,
    ) -> None:
        r"""
        Upload the contents of a folder to the mounted bucket.

        :param local_folder_path: Path to the folder to be uploaded
        :type local_folder_path: str

        :param key:
            An optional new name for the folder path on the bucket. Defaults to
            the same name as the local folder path
        :type key: str, optional

        :param show_progress_bar:
            Boolean choice of displaying a progress bar. Defaults to True
        :type show_progress_bar: bool, optional

        :param upload_mode:
            The upload mode of the transfer is any of the following:
                HCPHandler.UploadMode.STANDARD,
                HCPHandler.UploadMode.SIMPLE,
                HCPHandler.UploadMode.EQUAL_PARTS\n
        :type upload_mode: UploadMode, optional

        :param equal_parts:
            The number of equal parts that each file should be divided into when
            using the HCPHandler.UploadMode.EQUAL_PARTS mode. Default is 5
        :type equal_parts: int, optional

        :raises FileNotFoundError: If `path` does not exist
        """
        raise_path_error(local_folder_path)

        if not key:
            key = local_folder_path

        filenames = Path(local_folder_path).iterdir()

        for filename in filenames:
            self.upload_file(
                local_folder_path + filename.name,
                key + filename.name,
                show_progress_bar=show_progress_bar,
                upload_mode=upload_mode,
                equal_parts=equal_parts,
            )

    @check_mounted
    def delete_objects(self, keys: list[str]) -> str:
        """
        Delete a list of objects on the mounted bucket.

        :param keys: List of object names to be deleted
        :type keys: list[str]

        :raises IsFolderObjectError: If the provided object is a folder object

        :return: The result of the deletion
        :rtype: str
        """
        object_list = []
        does_not_exist = []
        for key in keys:
            if self.object_exists(key):
                if key[-1] == "/":
                    raise IsFolderObjectError(
                        'The object "'
                        + key
                        + '" is a folder object. Please use the `delete_folder`'
                        + "method for this object",
                    )
                object_list.append({"Key": key})
            else:
                does_not_exist.append(key)

        result = ""
        if object_list:
            deletion_dict = {"Objects": object_list}
            response: dict = self.s3_client.delete_objects(
                Bucket=self.bucket_name,
                Delete=deletion_dict,
            )

            deleted_files: list = [d["Key"] for d in response["Deleted"]]
            result += "The following was successfully deleted: \n" + "\n".join(
                deleted_files,
            )

        if does_not_exist:
            result += (
                "The following could not be deleted because they didn't "
                "exist:\n" + "\n".join(does_not_exist)
            )

        return result

    @check_mounted
    def delete_object(self, key: str) -> str:
        """
        Delete a single object in the mounted bucket.

        :param key: The object to be deleted
        :type key: str

        :raises IsFolderObject: If the provided object is a folder object

        :return: The result of the deletion
        :rtype: str
        """
        return self.delete_objects([key])

    @check_mounted
    def delete_folder(self, key: str) -> str:
        """
        Delete a folder of objects in the mounted bucket.
        If there are subfolders, a `SubfolderException` is raised

        :param key: The folder of objects to be deleted
        :type key: str

        :raises ObjectDoesNotExistError: If an object does not exist

        :raises SubfolderError: If there are subfolders

        :return: The result of the deletion
        :rtype: str
        """  # noqa: D400, D415
        if key[-1] != "/":
            key += "/"

        objects: list[dict[str, Any]] = list(
            self.list_objects(
                key,
                output_mode=HCPHandler.ListObjectsOutputMode.MINIMAL,
            ),
        )

        if not self.object_exists(key):
            raise ObjectDoesNotExistError(
                '"' + key + '"' + " does not exist",
            )

        # If the folder object is empty, delete the object itself. Since
        # `delete_objects` was only made for file objects in mind then
        if not objects:
            result = '"' + key + '"' + " was deleted"
        else:
            for hcp_object in objects:
                if not hcp_object["IsFile"]:
                    raise SubfolderError(
                        'There is at least one subfolder in "'
                        + key
                        + '". Please remove all subfolders before deleting "'
                        + key
                        + '" itself',
                    )

            result = self.delete_objects([obj["Key"] for obj in objects])

        # Delete the folder object itself separately
        self.s3_client.delete_object(
            Bucket=self.bucket_name,
            Key=key,
        )

        return result

    @check_mounted
    def copy_file(
        self,
        source_key: str,
        destination_key: str,
        destination_bucket: str = "",
    ) -> None:
        """
        Copy a file object within the HCP.

        :param source_key: The key to the object to be copied
        :type source_key: str

        :param destination_key: The key to where the object will be copied to
        :type destination_key: str

        :param destination_bucket:
            The destination bucket, defaults to the mounted bucket
        :type destination_bucket: str
        """
        file_size: int = self.s3_client.head_object(
            Bucket=self.bucket_name,
            Key=source_key,
        )["ContentLength"]
        with tqdm(
            total=file_size,
            unit="B",
            unit_scale=True,
            desc=source_key,
        ) as pbar:
            self.s3_client.copy(
                {"Bucket": self.bucket_name, "Key": source_key},
                destination_bucket if destination_bucket else self.bucket_name,
                destination_key,
                Callback=lambda bytes_transferred: pbar.update(
                    bytes_transferred,
                ),
            )

    @check_mounted
    def move_file(
        self,
        source_key: str,
        destination_key: str,
        destination_bucket: str = "",
    ) -> None:
        """
        Move a file `source_key` to `destination_key`.

        :param source_key: The key to the object to be moved
        :type source_key: str

        :param destination_key: The key to where the object will be moved to
        :type destination_key: str

        :param destination_bucket:
            The destination bucket, defaults to the mounted bucket
        :type destination_bucket: str
        """
        self.copy_file(source_key, destination_key, destination_bucket)
        self.delete_object(source_key)

    # ---------------------------- Search methods ----------------------------

    @check_mounted
    def search_in_bucket(
        self,
        search_string: str,
        case_sensitive: bool = False,
    ) -> Generator:
        """
        Simple search method using exact substrings in order to find certain
        objects. Case insensitive by default. Does not utilise the HCI

        :param search_string: Substring to be used in the search
        :type search_string: str

        :param case_sensitive: Case sensitivity. Defaults to False
        :type case_sensitive: bool, optional

        :return: A generator of objects based on the search string
        :rtype: Generator
        """  # noqa: D400, D415
        return self.fuzzy_search_in_bucket(search_string, case_sensitive, 100)

    @check_mounted
    def fuzzy_search_in_bucket(
        self,
        search_string: str,
        case_sensitive: bool = False,
        threshold: int = 80,
    ) -> Generator:
        """
        Fuzzy search implementation based on the `RapidFuzz` library.

        :param search_string: Substring to be used in the search
        :type search_string: str

        :param case_sensitive: Case sensitivity. Defaults to False
        :type case_sensitive: bool, optional

        :param threshold: The fuzzy search similarity score. Defaults to 80
        :type threshold: int, optional

        :return: A generator of objects based on the search string
        :rtype: Generator
        """
        msg = "This method is currently not implemented"
        raise NotImplementedError(msg)
        processor = None if case_sensitive else utils.default_process

        full_list = peekable(self.list_objects())

        full_list_names_only = peekable(
            obj["Key"]
            for obj in self.list_objects(
                output_mode=HCPHandler.ListObjectsOutputMode.MINIMAL,
                list_all_bucket_objects=True,
            )
        )

        for _, score, index in process.extract_iter(
            search_string,
            full_list_names_only,
            scorer=fuzz.partial_ratio,
            processor=processor,
        ):
            if score >= threshold:
                yield full_list[index]

    # ---------------------------- ACL methods ----------------------------

    @check_mounted
    def get_object_acl(self, key: str) -> dict:
        """
        Get the object Access Control List (ACL).

        :param key: The name of the object
        :type key: str

        :return: Return the ACL in the shape of a dictionary
        :rtype: dict
        """
        response: dict = self.s3_client.get_object_acl(
            Bucket=self.bucket_name,
            Key=key,
        )
        return response

    @check_mounted
    def get_bucket_acl(self) -> dict:
        """
        Get the bucket Access Control List (ACL).

        :return: Return the ACL in the shape of a dictionary
        :rtype: dict
        """
        response: dict = self.s3_client.get_bucket_acl(
            Bucket=self.bucket_name,
        )
        return response

    @check_mounted
    def modify_single_object_acl(
        self,
        key: str,
        user_ID: str,
        permission: str,
    ) -> None:
        r"""
        Modify permissions for a user in the Access Control List (ACL) for one
        object.

        :param key: The name of the object
        :type key: str

        :param user_ID: The user name. Can either be the DisplayName or user_ID
        :type user_ID: str

        :param permission:
            What permission to be set. Valid options are:
                * FULL_CONTROL
                * WRITE
                * WRITE_ACP
                * READ
                * READ_ACP\n
        :type permission: str
        """
        self.s3_client.put_object_acl(
            Bucket=self.bucket_name,
            Key=key,
            AccessControlPolicy=create_access_control_policy(
                {user_ID: permission},
            ),
        )

    @check_mounted
    def modify_single_bucket_acl(self, user_ID: str, permission: str) -> None:
        r"""
        Modify permissions for a user in the Access Control List (ACL) for the
        mounted bucket.

        :param user_ID: The user name. Can either be the DisplayName or user_ID
        :type user_ID: str

        :param permission:
            What permission to be set. Valid options are:
                * FULL_CONTROL
                * WRITE
                * WRITE_ACP
                * READ
                * READ_ACP\n
        :type permission: str
        """
        self.s3_client.put_bucket_acl(
            Bucket=self.bucket_name,
            AccessControlPolicy=create_access_control_policy(
                {user_ID: permission},
            ),
        )

    @check_mounted
    def modify_object_acl(
        self,
        key_user_ID_permissions: dict[str, dict[str, str]],
    ) -> None:
        r"""
        Modifies  permissions to multiple objects, see below.

        In order to add permissions for multiple objects, we make use of a
        dictionary of a dictionary:
        :py:obj:`key_user_ID_permissions = {key : {user_ID : permission}}`.
        So for every object (key), we set the permissions for every user ID for
        that object.

        :param key_user_ID_permissions:
            The dictionary containing object name and user_id-permission
            dictionary
        :type key_user_ID_permissions: dict[str, dict[str, str]]
        """
        for key, user_ID_permissions in key_user_ID_permissions.items():
            self.s3_client.put_object_acl(
                Bucket=self.bucket_name,
                Key=key,
                AccessControlPolicy=create_access_control_policy(
                    user_ID_permissions,
                ),
            )

    @check_mounted
    def modify_bucket_acl(self, user_ID_permissions: dict[str, str]) -> None:
        """
        Modify permissions for multiple users for the mounted bucket.

        :param user_ID_permissions:
            The dictionary containing the user name and the corresponding
            permission to be set to that user
        :type user_ID_permissions: dict[str, str]
        """
        self.s3_client.put_bucket_acl(
            Bucket=self.bucket_name,
            AccessControlPolicy=create_access_control_policy(
                user_ID_permissions,
            ),
        )
