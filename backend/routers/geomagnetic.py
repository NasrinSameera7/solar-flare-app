from fastapi import APIRouter
from services.nasa_client import get_geomagnetic_storms
from services.noaa_client import get_kp_index_1hour, get_geomagnetic_forecast
from services.cache import cache_get, cache_set

router = APIRouter()

@router.get("/geomagnetic")
async def get_geomagnetic():
    """Return geomagnetic storm data and Kp index."""
    cache_key = "geomagnetic"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    storms, kp_data, forecast = await _fetch_all()

    result = {
        "storms": [
            {
                "id": s.get("gstID", ""),
                "start_time": s.get("startTime", ""),
                "all_kp_index": s.get("allKpIndex", []),
            }
            for s in storms
        ],
        "kp_index_72h": kp_data,
        "forecast": forecast[:12] if forecast else [],
    }

    await cache_set(cache_key, result, ttl_seconds=300)
    return result


async def _fetch_all():
    import asyncio
    return await asyncio.gather(
        get_geomagnetic_storms(days=30),
        get_kp_index_1hour(),
        get_geomagnetic_forecast(),
    )
