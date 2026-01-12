# -------------- Parsing exceptions --------------


class NotAValidTenantError(Exception):
    """
    The given tenant name is not valid.
    """


class UnableToParseEndpointError(Exception):
    """
    The given endpoint URL was not correctly parsed.
    """


# -------------- MAPI request exceptions --------------
class NotSufficientPermissionsError(Exception):
    """
    The given permissions where not sufficient when making a MAPI request (403).
    """

class NotFoundError(Exception):
    """
    The given request path was not found when making a MAPI request (404).
    """

# -------------- Bucket exceptions --------------
class NoBucketMountedError(Exception):
    """
    No bucket has been mounted before using a method that require it.
    """


class BucketNotFoundError(Exception):
    """
    The bucket could not be found.
    """


class BucketForbiddenError(Exception):
    """
    The credentials used do not have permission to reach this bucket.
    """


# -------------- Bucket object exceptions --------------


class ObjectAlreadyExistError(Exception):
    """
    The object already exist on the mounted bucket.
    """


class ObjectDoesNotExistError(Exception):
    """
    The object does not exist on the mounted bucket.
    """


class IsFolderObjectError(Exception):
    """
    The object on the mounted bucket is a folder.
    """


class SubfolderError(Exception):
    """
    There is at least one subfolder in the given path on the mounted bucket.
    """


class DownloadLimitReachedError(Exception):
    """
    Download limit was reached while downloading file objects from the
    mounted bucket.
    """


# -------------- File system exceptions --------------


class UnallowedCharacterError(Exception):
    """
    A character that is not allowed was used.
    """
