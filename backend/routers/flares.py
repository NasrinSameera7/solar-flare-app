from fastapi import APIRouter
from services.nasa_client import get_solar_flares
from services.cache import cache_get, cache_set

router = APIRouter()

@router.get("/flares")
async def get_flares(days: int = 30):
    """Return recent solar flare events."""
    cache_key = f"flares_{days}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    raw = await get_solar_flares(days=days)
    result = []
    for f in raw:
        result.append({
            "id": f.get("flrID", ""),
            "begin_time": f.get("beginTime", ""),
            "peak_time": f.get("peakTime", ""),
            "end_time": f.get("endTime", ""),
            "class_type": f.get("classType", ""),
            "source_location": f.get("sourceLocation", ""),
            "active_region": f.get("activeRegionNum"),
            "linked_events": len(f.get("linkedEvents") or []),
        })

    # Sort by begin_time descending
    result.sort(key=lambda x: x["begin_time"] or "", reverse=True)
    await cache_set(cache_key, result, ttl_seconds=300)
    return result
