from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.schemas import MultiCityRequest, RoadTripRequest
from app.services.multicity import multicity
from app.services.rate_limit import limiter
from app.services.roadtrip import RoadTripUnavailable, roadtrip

router = APIRouter(prefix="/api/roadtrip", tags=["roadtrip"])


def _check_limit(request: Request, session_id: str | None, kind: str) -> None:
    ip = request.client.host if request.client else "unknown"
    identity = session_id or f"anonymous:{ip}"
    session_limit = (
        settings.max_roadtrip_plan_per_hour if kind == "plan"
        else settings.max_roadtrip_route_per_hour
    )
    ip_limit = (
        settings.max_roadtrip_plan_ip_per_hour if kind == "plan"
        else settings.max_roadtrip_route_ip_per_hour
    )
    if not limiter.check_many([
        (f"roadtrip-{kind}-ip:{ip}", ip_limit, 3600),
        (f"roadtrip-{kind}-session:{identity}", session_limit, 3600),
    ]):
        raise HTTPException(429, "Road-trip request limit exceeded")


@router.post("/route")
def build_roadtrip_route(payload: RoadTripRequest, request: Request):
    _check_limit(request, payload.ma_phien, "route")
    try:
        return roadtrip.route(payload)
    except RoadTripUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/plan")
def build_multicity_plan(payload: MultiCityRequest, request: Request):
    _check_limit(request, payload.ma_phien, "plan")
    try:
        return multicity.plan(payload)
    except RoadTripUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
