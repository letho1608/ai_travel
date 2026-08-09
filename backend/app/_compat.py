"""Minimal Python 3.10 compatibility shim.

`datetime.UTC` only exists from Python 3.11. On 3.10 it is exactly equal to
`datetime.timezone.utc`, so we patch it in so the rest of the codebase can use
`from datetime import UTC` uniformly on every supported version.
"""

import datetime as _datetime


def install() -> None:
    if not hasattr(_datetime, "UTC"):
        _datetime.UTC = _datetime.timezone.utc