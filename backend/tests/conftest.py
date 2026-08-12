import datetime as _datetime

if not hasattr(_datetime, "UTC"):
    _datetime.UTC = _datetime.timezone.utc

import os

os.environ.setdefault("PLAN_ROUTE_GEOMETRY", "0")
