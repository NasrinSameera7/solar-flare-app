from fastapi import APIRouter
from services.noaa_client import get_noaa_alerts, get_3day_forecast
from services.cache import cache_get, cache_set

router = APIRouter()

@router.get("/alerts")
async def get_alerts():
    """Return active NOAA space weather alerts."""
    cache_key = "alerts"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    raw_alerts = await get_noaa_alerts()
    # Normalize alert structure
    alerts = []
    for a in raw_alerts:
        if isinstance(a, dict):
            alerts.append({
                "product_id": a.get("product_id", ""),
                "issue_datetime": a.get("issue_datetime", ""),
                "message": a.get("message", ""),
                "serial_number": a.get("serial_number", ""),
            })

    await cache_set(cache_key, alerts, ttl_seconds=300)
    return alerts


@router.get("/forecast")
async def get_forecast():
    """Return 3-day NOAA space weather forecast text."""
    cache_key = "forecast_3day"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    data = await get_3day_forecast()
    await cache_set(cache_key, data, ttl_seconds=3600)
    return data
