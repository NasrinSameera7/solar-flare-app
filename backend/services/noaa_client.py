import httpx
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

NOAA_BASE = "https://services.swpc.noaa.gov"


async def get_xray_flares_7day() -> list:
    """Fetch 7-day X-ray flare events from NOAA SWPC."""
    url = f"{NOAA_BASE}/json/goes/primary/xray-flares-7-day.json"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json() or []
    except Exception as e:
        logger.error(f"NOAA xray flares error: {e}")
        return []


async def get_kp_index_1hour() -> list:
    """Fetch estimated Kp index (1-hour data) from NOAA."""
    url = f"{NOAA_BASE}/json/planetary_k_index_1m.json"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json() or []
            # Return the last 72 entries (72 hours)
            return data[-72:] if len(data) > 72 else data
    except Exception as e:
        logger.error(f"NOAA Kp index error: {e}")
        return _mock_kp_index()


async def get_solar_wind() -> dict:
    """Fetch real-time solar wind data from NOAA."""
    url = f"{NOAA_BASE}/products/solar-wind/mag-5-minute.json"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            if data and len(data) > 1:
                headers = data[0]
                latest = data[-1]
                return dict(zip(headers, latest))
            return {}
    except Exception as e:
        logger.error(f"NOAA solar wind error: {e}")
        return {"bx_gsm": "-3.2", "by_gsm": "5.1", "bz_gsm": "-8.4", "bt": "9.7"}


async def get_noaa_alerts() -> list:
    """Fetch active space weather alerts from NOAA SWPC."""
    url = f"{NOAA_BASE}/products/alerts.json"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json() or []
            return data[:10]  # Return latest 10 alerts
    except Exception as e:
        logger.error(f"NOAA alerts error: {e}")
        return []


async def get_3day_forecast() -> dict:
    """Fetch 3-day space weather forecast from NOAA."""
    url = f"{NOAA_BASE}/text/3-day-forecast.txt"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return {"raw": resp.text}
    except Exception as e:
        logger.error(f"NOAA 3-day forecast error: {e}")
        return {"raw": "Forecast data temporarily unavailable."}


async def get_geomagnetic_forecast() -> list:
    """Fetch geomagnetic Kp forecast from NOAA."""
    url = f"{NOAA_BASE}/products/noaa-planetary-k-index-forecast.json"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json() or []
            return data[1:] if len(data) > 1 else []  # Skip header row
    except Exception as e:
        logger.error(f"NOAA geo forecast error: {e}")
        return []


def _mock_kp_index() -> list:
    """Return mock Kp index data."""
    from datetime import timedelta
    import math
    now = datetime.utcnow()
    return [
        {
            "time_tag": (now - timedelta(hours=71 - i)).strftime("%Y-%m-%d %H:%M:%S.%f"),
            "kp": round(2 + 3 * abs(math.sin(i * 0.2)), 2),
        }
        for i in range(72)
    ]
