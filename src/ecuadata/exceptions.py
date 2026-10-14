"""Exceptions raised by ecuadata."""


class EcuadataError(Exception):
    """Base class for every error raised by ecuadata."""


class SourceUnavailableError(EcuadataError):
    """The publisher could not be reached, or the requested file does not exist."""


class ParseError(EcuadataError):
    """A downloaded file did not have the layout the parser expects.

    This usually means the publisher changed the file format. Please open an issue.
    """


class OfflineError(EcuadataError):
    """Offline mode is on and the requested data is not in the cache."""
