from fastapi import APIRouter, Request
from services.nasa_client import get_solar_flares, get_cme_events
from services.noaa_client import get_kp_index_1hour
from services.cache import cache_get, cache_set, get_prediction_history

router = APIRouter()

@router.get("/predict")
async def predict(request: Request):
    """Run ML prediction for next 24-hour solar flare class."""
    cache_key = "prediction_latest"
    cached = await cache_get(cache_key)
    if cached:
        return cached

    ml_engine = request.app.state.ml_engine
    flares, cmes, kp = await _fetch_inputs()
    result = await ml_engine.predict(flares, cmes, kp)

    await cache_set(cache_key, result, ttl_seconds=180)
    return result


@router.get("/predict/history")
async def prediction_history(hours: int = 48):
    """Return historical prediction records."""
    return await get_prediction_history(hours=hours)


async def _fetch_inputs():
    import asyncio
    return await asyncio.gather(
        get_solar_flares(days=7),
        get_cme_events(days=7),
        get_kp_index_1hour(),
    )
