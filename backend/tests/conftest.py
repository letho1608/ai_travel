import datetime as _datetime

if not hasattr(_datetime, "UTC"):
    _datetime.UTC = _datetime.timezone.utc

import os

os.environ["AI_MODE"] = "offline"
os.environ["APP_ENV"] = "local"
os.environ["USE_DURABLE_LOCAL"] = "false"
os.environ["PLAN_ROUTE_GEOMETRY"] = "0"
os.environ["SUPPORT_ADMIN_TOKEN"] = "local-support-dev"
