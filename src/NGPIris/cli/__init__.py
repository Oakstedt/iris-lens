import sys
from collections.abc import Generator
from json import dump
from pathlib import Path
from typing import Any

import click
import lazy_table as lt
from click.core import Context
from tabulate import tabulate

from NGPIris import HCPHandler
from NGPIris.cli.helpers import (
    add_trailing_slash,
    create_HCPHandler,
    download_file,
    download_folder,
    ensure_destination_dir,
    object_is_folder,
)
from NGPIris.cli.sections import SectionedGroup
from NGPIris.hcp.exceptions import IsFolderObjectError, ObjectDoesNotExistError


@click.group(cls=SectionedGroup)
@click.option(
    "-c",
    "--credentials",
    help="Path to a JSON file with credentials",
)
@click.option(
    "--debug",
    help="Get the debug log for running a command",
    is_flag=True,
)
@click.option(
    "-tc",
    "--transfer_config",
    help="Path for using a custom transfer config for uploads or downloads",
)
@click.version_option(package_name="NGPIris")
@click.pass_context
def cli(
    context: Context,
    credentials: str,
    debug: bool,
    transfer_config: str,
) -> None:
    """
    NGP Intelligence and Repository Interface Software, IRIS.
    """


# ---------------------------- Object commands ----------------------------


@cli.command(
    section="Object commands",
    short_help="Copy objects in a bucket/namespace on the HCP.",
)
@click.argument("bucket")
@click.argument("source")
@click.argument("destination")
@click.option(
    "-db",
    "--destination_bucket",
    help="Choose another destination bucket than the source bucket",
    default="",
)
@click.option(
    "-dr",
    "--dry_run",
    help=(
        "Simulate the command execution without making actual changes. "
        "Useful for testing and verification"
    ),
    is_flag=True,
)
@click.pass_context
def copy(  # noqa: PLR0913
    context: Context,
    bucket: str,
    source: str,
    destination: str,
    destination_bucket: str,
    dry_run: bool,
) -> None:
    """
    Copy objects in a bucket/namespace on the HCP.

    BUCKET is the bucket where SOURCE is.

    SOURCE is the object to be copied.

    DESTINATION is the destination path (the path where the object will be
    copied to).
    """
    hcp_h: HCPHandler = create_HCPHandler(context)
    hcp_h.mount_bucket(bucket)
    if not dry_run:
        hcp_h.copy_file(source, destination, destination_bucket)
    else:
        click.echo(
            'This command would have copied the file object "' + source + '"',
        )


@cli.command(
    section="Object commands",
    short_help="Move objects in a bucket/namespace on the HCP.",
)
@click.argument("bucket")
@click.argument("source")
@click.argument("destination")
@click.option(
    "-db",
    "--destination_bucket",
    help="Choose another destination bucket than the source bucket",
    default="",
)
@click.option(
    "-dr",
    "--dry_run",
    help=(
        "Simulate the command execution without making actual changes. "
        "Useful for testing and verification"
    ),
    is_flag=True,
)
@click.pass_context
def move(  # noqa: PLR0913
    context: Context,
    bucket: str,
    source: str,
    destination: str,
    destination_bucket: str,
    dry_run: bool,
) -> None:
    """
    Move objects in a bucket/namespace on the HCP.

    BUCKET is the bucket where SOURCE is.

    SOURCE is the object to be moved.

    DESTINATION is the destination path (the path where the object will be
    moved to).
    """
    hcp_h: HCPHandler = create_HCPHandler(context)
    hcp_h.mount_bucket(bucket)
    if not dry_run:
        hcp_h.move_file(source, destination, destination_bucket)
    else:
        click.echo(
            'This command would have moved the file object "' + source + '"',
        )


@cli.command(
    section="Object commands",
    short_help="Delete objects in a bucket/namespace on the HCP.",
)
@click.argument("bucket")
@click.argument("hcp_object")
@click.option(
    "-dr",
    "--dry_run",
    help=(
        "Simulate the command execution without making actual changes. "
        "Useful for testing and verification"
    ),
    is_flag=True,
)
@click.option(
    "-m",
    "--mode",
    type=click.Choice(
        ["file", "folder"],
        case_sensitive=False,
    ),
    default="folder",
    help=(
        "Allows for selection of between two modes: `files` or `folder`. "
        "`files` is for deleting individual files, while `folder` is for "
        "deleting a folder. `folder` is default mode"
    ),
)
@click.pass_context
def delete(
    context: Context,
    bucket: str,
    hcp_object: str,
    dry_run: bool,
    mode: str,
) -> None:
    """
    Delete objects in a bucket/namespace on the HCP.

    BUCKET is the name of the bucket where the object to be deleted exist.

    HCP_OBJECT is the name of the object to be deleted.
    """
    hcp_h: HCPHandler = create_HCPHandler(context)
    hcp_h.mount_bucket(bucket)
    if not dry_run:
        match mode:
            case "files":
                try:
                    click.echo(hcp_h.delete_object(hcp_object))
                except IsFolderObjectError:
                    click.echo(
                        'The object "'
                        + hcp_object
                        + '" is a folder object. Please use `-m folder` for '
                        + "this object",
                        err=True,
                    )
                    sys.exit(1)
            case "folder":
                try:
                    click.echo(hcp_h.delete_folder(hcp_object))
                except ObjectDoesNotExistError:
                    click.echo(
                        'The object "'
                        + hcp_object
                        + '" does not exist as folder. If your intention was to'
                        + "delete a single file object, please use `-m file`"
                        + "for this object",
                        err=True,
                    )
                    sys.exit(1)
    else:
        match mode:
            case "files":
                click.echo(
                    'This command would have deleted the file object "'
                    + hcp_object
                    + '"',
                )
            case "folder":
                click.echo(
                    'By deleting "'
                    + hcp_object
                    + '", the following file objects would have been deleted '
                    + "(this list excludes any potential sub-folders):",
                )
                lt.stream(
                    hcp_h.list_objects(
                        hcp_object,
                        files_only=True,
                    ),
                    headers="keys",
                )


@cli.command(
    section="Object commands",
    short_help="Download a file or folder from a bucket/namespace on the HCP.",
)
@click.argument("bucket")
@click.argument("source")
@click.argument("destination")
@click.option(
    "-f",
    "--force",
    help=(
        "Overwrite existing file with the same name (single file download only)"
    ),
    is_flag=True,
)
@click.option(
    "-iw",
    "--ignore_warning",
    help="Ignore the download limit",
    is_flag=True,
)
@click.option(
    "-dr",
    "--dry_run",
    help=(
        "Simulate the command execution without making actual changes. "
        "Useful for testing and verification"
    ),
    is_flag=True,
)
@click.pass_context
def download(  # noqa: PLR0913
    context: Context,
    bucket: str,
    source: str,
    destination: str,
    force: bool,
    ignore_warning: bool,
    dry_run: bool,
) -> None:
    """
    Download a file or folder from a bucket/namespace from the HCP.

    BUCKET is the name of the download source bucket.

    SOURCE is the path to the object or object folder to be downloaded.

    DESTINATION is the folder where the downloaded object or object folder is to
    be stored locally.
    """
    hcp_h: HCPHandler = create_HCPHandler(context)
    hcp_h.mount_bucket(bucket)

    destination_path = ensure_destination_dir(destination)

    is_folder = object_is_folder(source, hcp_h)

    if dry_run:
        if hcp_h.object_exists(source):
            if is_folder:
                click.echo(
                    'This command would have downloaded the folder "'
                    + source
                    + '". If you wish to know the contents of this folder, '
                    + "use the 'list-objects' command",
                )
            else:
                click.echo(
                    'This command would have downloaded the object "'
                    + source
                    + '"',
                )
        else:
            click.echo(
                '"' + source + '" does not exist',
            )
        return

    if is_folder:
        download_folder(source, destination_path, ignore_warning, hcp_h)
    else:
        download_file(source, destination_path, ignore_warning, force, hcp_h)


@cli.command(
    section="Object commands",
    short_help="List the objects in a certain bucket/namespace on the HCP.",
)
@click.argument("bucket")
@click.argument("path", required=False)
@click.option(
    "-p",
    "--pagination",
    help="Output as a paginator",
    default=False,
    is_flag=True,
)
@click.option(
    "-fo",
    "--files-only",
    help="Output only file objects",
    default=False,
    is_flag=True,
)
@click.option(
    "-e",
    "--extended-information",
    help="Output the fully extended information for each object",
    default=False,
    is_flag=True,
)
@click.pass_context
def list_objects(  # noqa: PLR0913
    context: Context,
    bucket: str,
    path: str,
    pagination: bool,
    files_only: bool,
    extended_information: bool,
) -> None:
    """
    List the objects in a certain bucket/namespace on the HCP.

    BUCKET is the name of the bucket in which to list its objects.

    PATH is an optional argument for where to list the objects
    """

    def list_objects_generator(
        hcp_h: HCPHandler,
        path: str,
        files_only: bool,
        output_mode: HCPHandler.ListObjectsOutputMode,
    ) -> Generator[str, Any, None]:
        """
        Handle object list as a paginator that `click` can handle.
        It works slightly different from `list_objects` in `hcp.py` in order to
        make the output printable in a terminal
        """  # noqa: D415, D400
        objects = hcp_h.list_objects(
            path,
            output_mode=output_mode,
            files_only=files_only,
        )
        for obj in objects:
            yield str(obj) + "\n"

    hcp_h: HCPHandler = create_HCPHandler(context)
    hcp_h.mount_bucket(bucket)
    output_mode = (
        HCPHandler.ListObjectsOutputMode.EXTENDED
        if extended_information
        else HCPHandler.ListObjectsOutputMode.SIMPLE
    )

    if path:
        path_with_slash = add_trailing_slash(path)

        if not hcp_h.object_exists(path_with_slash):
            msg = path_with_slash + " does not exist"
            raise ObjectDoesNotExistError(msg)
    else:
        path_with_slash = ""

    if pagination:
        click.echo_via_pager(
            list_objects_generator(
                hcp_h,
                path_with_slash,
                files_only,
                output_mode,
            ),
        )
    else:
        lt.stream(
            hcp_h.list_objects(
                path_with_slash,
                output_mode=output_mode,
                files_only=files_only,
            ),
            headers="keys",
        )


@cli.command(
    section="Object commands",
    short_help="Upload a file or folder from a bucket/namespace on the HCP.",
)
@click.argument("bucket")
@click.argument("source")
@click.argument("destination")
@click.option(
    "-dr",
    "--dry_run",
    help=(
        "Simulate the command execution without making actual changes. "
        "Useful for testing and verification"
    ),
    is_flag=True,
)
@click.option(
    "-um",
    "--upload_mode",
    help="""
    Choose an upload method. Default upload mode is STANDARD which uses a basic
    multipart upload. Use another mode than STANDARD if that mode misbehaves
    """,
    type=click.Choice(
        ["STANDARD", "SIMPLE", "EQUAL_PARTS"],
        case_sensitive=False,
    ),
    default="STANDARD",
)
@click.option(
    "-ep",
    "--equal_parts",
    help="""
    Supplementary option when using the EQUAL_PARTS upload mode. Splits each
    file into a given number of parts. Must be a positive integer
    """,
    type=int,
    default=5,
)
@click.pass_context
def upload(  # noqa: PLR0913
    context: Context,
    bucket: str,
    source: str,
    destination: str,
    dry_run: bool,
    upload_mode: str,
    equal_parts: int,
) -> None:
    """
    Upload files to a bucket/namespace on the HCP.

    BUCKET is the name of the upload destination bucket.

    SOURCE is the path to the file or folder of files to be uploaded.

    DESTINATION is the destination path on the HCP.
    """
    if equal_parts <= 0:
        click.echo(
            "Error: --equal_parts value must be a positive integer",
            err=True,
        )
        sys.exit(1)

    upload_mode_choice = HCPHandler.UploadMode(upload_mode.lower())

    hcp_h: HCPHandler = create_HCPHandler(context)
    hcp_h.mount_bucket(bucket)
    destination = add_trailing_slash(destination)
    if Path(source).is_dir():
        source = add_trailing_slash(source)
        if dry_run:
            click.echo(
                'This command would have uploaded the folder "'
                + source
                + '" to "'
                + destination
                + '"',
            )
        else:
            hcp_h.upload_folder(
                source,
                destination,
                upload_mode=upload_mode_choice,
                equal_parts=equal_parts,
            )
    else:
        file_name = Path(source).name
        destination += file_name
        if dry_run:
            click.echo(
                'This command would have uploaded the file "'
                + source
                + '" to "'
                + destination
                + '"',
            )
        else:
            hcp_h.upload_file(
                source,
                destination,
                upload_mode=upload_mode_choice,
                equal_parts=equal_parts,
            )


# ---------------------------- Bucket commands ----------------------------


@cli.command(
    section="Bucket commands",
    short_help="Create a bucket/namespace on the HCP.",
)
@click.argument("bucket")
@click.option(
    "-dr",
    "--dry_run",
    help=(
        "Simulate the command execution without making actual changes. "
        "Useful for testing and verification"
    ),
    is_flag=True,
)
@click.pass_context
def create_bucket(
    context: Context,
    bucket: str,
    dry_run: bool,
) -> None:
    """
    Create a bucket/namespace on the HCP.
    """
    hcp_h: HCPHandler = create_HCPHandler(context)
    if not dry_run:
        hcp_h.create_bucket(bucket)
        click.echo(bucket + " was successfully created")
    else:
        click.echo(
            'This command would have created a bucket called "' + bucket + '"',
        )


@cli.command(
    section="Bucket commands",
    short_help="Delete a bucket/namespace on the HCP.",
)
@click.argument("bucket")
@click.option(
    "-dr",
    "--dry_run",
    help=(
        "Simulate the command execution without making actual changes. "
        "Useful for testing and verification"
    ),
    is_flag=True,
)
@click.pass_context
def delete_bucket(
    context: Context,
    bucket: str,
    dry_run: bool,
) -> None:
    """
    Delete a bucket/namespace on the HCP.
    """
    hcp_h: HCPHandler = create_HCPHandler(context)
    if not dry_run:
        hcp_h.delete_bucket(bucket)
        click.echo(bucket + " was successfully deleted")
    else:
        click.echo(
            'This command would have deleted the bucket called "'
            + bucket
            + '"',
        )


@cli.command(
    section="Bucket commands",
    short_help="List the available buckets/namespaces on the HCP.",
)
@click.option(
    "-o",
    "--output_mode",
    help="Choose how verbose the output should",
    type=click.Choice(
        HCPHandler.ListBucketsOutputMode,
        case_sensitive=False,
    ),
    default=HCPHandler.ListBucketsOutputMode.SIMPLE,
)
@click.pass_context
def list_buckets(
    context: Context, output_mode: HCPHandler.ListBucketsOutputMode
) -> None:
    """
    List the available buckets/namespaces on the HCP.
    """
    hcp_h: HCPHandler = create_HCPHandler(context)
    click.echo(
        tabulate(
            hcp_h.list_buckets(output_mode),
            headers="keys",
            disable_numparse=True,
        )
    )


# ---------------------------- Search commands ----------------------------


@cli.command(
    section="Search commands",
    short_help=(
        "Make a simple search using substrings in a bucket/namespace on "
        "the HCP."
    ),
)
@click.argument("bucket")
@click.argument("search_string")
@click.option(
    "-cs",
    "--case_sensitive",
    help="Use case sensitivity? Default value is False",
    default=False,
    is_flag=True,
)
@click.pass_context
def simple_search(
    context: Context,
    bucket: str,
    search_string: str,
    case_sensitive: bool,
) -> None:
    """
    Make a simple search using substrings in a bucket/namespace on the HCP.

    NOTE: This command does not use the HCI. Instead, it uses a linear search of
    all the objects in the HCP. As such, this search might be slow.

    BUCKET is the name of the bucket in which to make the search.

    SEARCH_STRING is any string that is to be used for the search.
    """
    hcp_h: HCPHandler = create_HCPHandler(context)
    hcp_h.mount_bucket(bucket)
    list_of_results = hcp_h.search_in_bucket(
        search_string,
        case_sensitive=case_sensitive,
    )
    click.echo("Search results:")
    lt.stream(
        list_of_results,
        headers="keys",
    )


@cli.command(
    section="Search commands",
    short_help=(
        "Make a fuzzy search using a search string in a bucket/namespace"
        "on the HCP."
    ),
)
@click.argument("bucket")
@click.argument("search_string")
@click.option(
    "-cs",
    "--case_sensitive",
    help="Use case sensitivity? Default value is False",
    default=False,
    is_flag=True,
)
@click.option(
    "-t",
    "--threshold",
    help="Set the threshold for the fuzzy search score. Default value is 80",
    default=80,
)
@click.pass_context
def fuzzy_search(
    context: Context,
    bucket: str,
    search_string: str,
    case_sensitive: bool,
    threshold: int,
) -> None:
    """
    Make a fuzzy search using a search string in a bucket/namespace on the HCP.

    NOTE: This command does not use the HCI. Instead, it uses the RapidFuzz
    library in order to find objects in the HCP. As such, this search might be
    slow.

    BUCKET is the name of the bucket in which to make the search.

    SEARCH_STRING is any string that is to be used for the search.
    """
    hcp_h: HCPHandler = create_HCPHandler(context)
    hcp_h.mount_bucket(bucket)
    list_of_results = hcp_h.fuzzy_search_in_bucket(
        search_string,
        case_sensitive=case_sensitive,
        threshold=threshold,
    )
    click.echo("Search results:")
    lt.stream(
        list_of_results,
        headers="keys",
    )


# ---------------------------- Utility commands ----------------------------


@cli.command(section="Utility commands")
@click.argument("bucket")
@click.pass_context
def test_connection(context: Context, bucket: str) -> None:
    """
    Test the connection to a bucket/namespace.

    BUCKET is the name of the bucket for which a connection test should be made.
    """
    hcp_h: HCPHandler = create_HCPHandler(context)
    click.echo(hcp_h.test_connection(bucket))


# -------------------- Generate credentials command --------------------


@click.command()
@click.option(
    "--path",
    help="Path for where to put the new credentials file.",
    default="",
)
@click.option(
    "--name",
    help="""
    Custom name for the credentials file. Will filter out everything after a "."
    character, if any exist.
    """,
    default="credentials",
)
def iris_generate_credentials_file(path: str, name: str) -> None:
    """
    Generate blank credentials file for the HCI and HCP.

    WARNING: This file will store sensitive information (such as passwords) in
    plaintext.
    """
    credentials_dict = {
        "hcp": {
            "endpoint": "",
            "aws_access_key_id": "",
            "aws_secret_access_key": "",
        },
        "hci": {
            "username": "",
            "password": "",
            "address": "",
            "auth_port": "",
            "api_port": "",
        },
    }

    name = name.split(".")[0] + ".json"
    if path:
        if not path[-1] == "/":
            path += "/"

        file_path = name if path == "." else path + name

        if not Path(path).is_dir():
            Path(path).mkdir(parents=True)
    else:
        file_path = name

    with Path(file_path).open("w") as f:
        dump(credentials_dict, f, indent=4)
