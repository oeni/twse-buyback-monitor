"""Exception hierarchy.

Every failure mode raises explicitly. Nothing is swallowed and no partial
result is ever written to disk, because a corrupt baseline snapshot silently
turns into hundreds of bogus "new announcement" rows on the following run.
"""


class BuybackError(Exception):
    """Base class for all errors raised by this package."""


class StructureChanged(BuybackError):
    """The MOPS response no longer looks like the page we know how to parse.

    Raised when the title keyword is missing or when zero data rows survive
    column-count filtering. Both mean MOPS changed its markup: fail loudly
    rather than write an empty snapshot.
    """


class TruncatedResponse(BuybackError):
    """The MOPS response arrived incomplete.

    MOPS intermittently returns a response that is cut off partway through the
    table. The HTML still parses and still contains valid rows, so nothing
    downstream notices -- the tail of the table (high stock codes) simply
    vanishes. Overwriting the snapshot with that partial data is what produces
    the mass false-positive "new case" reports when the full response returns.
    """


class FetchError(BuybackError):
    """The HTTP request failed, or returned a status/encoding we cannot use."""
