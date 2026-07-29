import os
import httpx
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

NASA_API_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")
BASE_URL = "https://api.nasa.gov/DONKI"


def _date_range(days: int = 30):
    end = datetime.utcnow()
    start = end - timedelta(days=days)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


async def get_solar_flares(days: int = 30) -> list:
    """Fetch solar flare events from NASA DONKI."""
    start, end = _date_range(days)
    url = f"{BASE_URL}/FLR"
    params = {"startDate": start, "endDate": end, "api_key": NASA_API_KEY}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            if not data:
                return []
            return data
    except Exception as e:
        logger.error(f"NASA FLR fetch error: {e}")
        return _mock_flares()


async def get_cme_events(days: int = 30) -> list:
    """Fetch Coronal Mass Ejection events from NASA DONKI."""
    start, end = _date_range(days)
    url = f"{BASE_URL}/CME"
    params = {"startDate": start, "endDate": end, "api_key": NASA_API_KEY}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data if data else []
    except Exception as e:
        logger.error(f"NASA CME fetch error: {e}")
        return _mock_cme()


async def get_geomagnetic_storms(days: int = 30) -> list:
    """Fetch geomagnetic storm (GST) events from NASA DONKI."""
    start, end = _date_range(days)
    url = f"{BASE_URL}/GST"
    params = {"startDate": start, "endDate": end, "api_key": NASA_API_KEY}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data if data else []
    except Exception as e:
        logger.error(f"NASA GST fetch error: {e}")
        return []


async def get_sep_events(days: int = 30) -> list:
    """Fetch Solar Energetic Particle events from NASA DONKI."""
    start, end = _date_range(days)
    url = f"{BASE_URL}/SEP"
    params = {"startDate": start, "endDate": end, "api_key": NASA_API_KEY}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data if data else []
    except Exception as e:
        logger.error(f"NASA SEP fetch error: {e}")
        return []


def _mock_flares() -> list:
    """Return realistic mock flare data when API is unavailable."""
    now = datetime.utcnow()
    return [
        {
            "flrID": f"MOCK-{i}",
            "beginTime": (now - timedelta(days=i * 2)).strftime("%Y-%m-%dT%H:%MZ"),
            "peakTime": (now - timedelta(days=i * 2, hours=-1)).strftime("%Y-%m-%dT%H:%MZ"),
            "endTime": (now - timedelta(days=i * 2, hours=-2)).strftime("%Y-%m-%dT%H:%MZ"),
            "classType": cls,
            "sourceLocation": f"{'N' if i % 2 == 0 else 'S'}{10 + i * 3}{'E' if i % 3 == 0 else 'W'}{20 + i * 5}",
            "activeRegionNum": 13000 + i,
        }
        for i, cls in enumerate(["X1.5", "M4.2", "C8.3", "M2.1", "X2.3", "C5.1", "M6.7", "B9.2"])
    ]


def _mock_cme() -> list:
    """Return realistic mock CME data."""
    now = datetime.utcnow()
    return [
        {
            "activityID": f"CME-MOCK-{i}",
            "startTime": (now - timedelta(days=i * 3)).strftime("%Y-%m-%dT%H:%MZ"),
            "cmeAnalyses": [
                {
                    "speed": 400 + i * 150,
                    "type": "C" if i % 3 == 0 else "S",
                    "halfAngle": 20 + i * 5,
                }
            ],
            "note": f"Halo CME event {i + 1}",
        }
        for i in range(5)
    ]
