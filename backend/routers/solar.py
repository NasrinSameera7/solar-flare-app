from fastapi import APIRouter
from services.noaa_client import get_solar_wind
from services.cache import cache_get, cache_set

router = APIRouter()

@router.get("/solar-wind")
async def get_solar_wind_data():
    """Return real-time solar wind magnetic field data."""
    cache_key = "solar_wind"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    data = await get_solar_wind()
    await cache_set(cache_key, data, ttl_seconds=120)
    return data
