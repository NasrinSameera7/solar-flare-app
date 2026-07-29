from fastapi import APIRouter
from services.nasa_client import get_cme_events
from services.cache import cache_get, cache_set

router = APIRouter()

@router.get("/cme")
async def get_cme(days: int = 30):
    """Return recent Coronal Mass Ejection events."""
    cache_key = f"cme_{days}"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    raw = await get_cme_events(days=days)
    result = []
    for c in raw:
        analyses = c.get("cmeAnalyses") or []
        best = analyses[0] if analyses else {}
        result.append({
            "id": c.get("activityID", ""),
            "start_time": c.get("startTime", ""),
            "speed_kms": best.get("speed"),
            "type": best.get("type", ""),
            "half_angle": best.get("halfAngle"),
            "note": c.get("note", ""),
            "linked_events": len(c.get("linkedEvents") or []),
        })

    result.sort(key=lambda x: x["start_time"] or "", reverse=True)
    await cache_set(cache_key, result, ttl_seconds=300)
    return result
