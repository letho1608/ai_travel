import datetime as _datetime

if not hasattr(_datetime, "UTC"):
    _datetime.UTC = _datetime.timezone.utc
