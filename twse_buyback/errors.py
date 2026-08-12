"""Package exceptions."""


class BuybackError(Exception):
    """Base class for all errors raised by this package."""


class StructureChanged(BuybackError):
    """The MOPS response no longer matches the expected table structure."""


class TruncatedResponse(BuybackError):
    """MOPS did not return a complete table within the retry limit."""


class FetchError(BuybackError):
    """The HTTP request failed, or returned a status/encoding we cannot use."""
