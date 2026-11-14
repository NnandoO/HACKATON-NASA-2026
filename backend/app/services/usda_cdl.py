from concurrent.futures import ThreadPoolExecutor
import logging
import math
import re
from typing import Dict, List, Optional, Tuple

import httpx

from app.config import settings
from app.schemas import CdlCropYear
from app.services.geo_cache import geo_cache

logger = logging.getLogger(__name__)

# GRS80 / NAD83 CONUS Albers Equal Area (EPSG:5070)
_A = 6378137.0
_F = 1.0 / 298.257222101
_E2 = 2.0 * _F - _F * _F
_E = math.sqrt(_E2)
_LAT0 = math.radians(23.0)
_LON0 = math.radians(-96.0)
_LAT1 = math.radians(29.5)
_LAT2 = math.radians(45.5)

CDL_TO_CROP_ID: Dict[str, str] = {
    "corn": "maiz",
    "sweet corn": "maiz",
    "pop or orn corn": "maiz",
    "soybeans": "soja",
    "winter wheat": "trigo",
    "spring wheat": "trigo",
    "durum wheat": "trigo",
    "sorghum": "sorgo",
    "alfalfa": "alfalfa",
    "dry beans": "frijol",
    "sunflower": "girasol",
    "chick peas": "garbanzo",
}

_RESULT_CAT_RE = re.compile(r'value:\s*(\d+)\s*,\s*category:\s*"([^"]+)"')


def _albers_q(lat_rad: float) -> float:
    sin_phi = math.sin(lat_rad)
    es = _E * sin_phi
    return (1.0 - _E2) * (
        sin_phi / (1.0 - _E2 * sin_phi * sin_phi)
        - (1.0 / (2.0 * _E)) * math.log((1.0 - es) / (1.0 + es))
    )


def _albers_m(lat_rad: float) -> float:
    sin_phi = math.sin(lat_rad)
    return math.cos(lat_rad) / math.sqrt(1.0 - _E2 * sin_phi * sin_phi)


def wgs84_to_epsg5070(lat: float, lon: float) -> Tuple[float, float]:
    """Project WGS84 (lat, lon) coordinates to NAD83 / Conus Albers (EPSG:5070) meters."""
    phi = math.radians(lat)
    lam = math.radians(lon)
    m1 = _albers_m(_LAT1)
    m2 = _albers_m(_LAT2)
    q0 = _albers_q(_LAT0)
    q1 = _albers_q(_LAT1)
    q2 = _albers_q(_LAT2)
    q = _albers_q(phi)

    n = (m1 * m1 - m2 * m2) / (q2 - q1)
    c = m1 * m1 + n * q1
    rho0 = _A * math.sqrt(max(0.0, c - n * q0)) / n
    rho = _A * math.sqrt(max(0.0, c - n * q)) / n
    theta = n * (lam - _LON0)
    x = rho * math.sin(theta)
    y = rho0 - rho * math.cos(theta)
    return round(x, 1), round(y, 1)


def is_conus_coordinate(lat: float, lon: float) -> bool:
    return 24.5 <= lat <= 49.5 and -125.0 <= lon <= -66.0


def parse_cdl_xml(xml_text: str, year: int) -> Optional[CdlCropYear]:
    match = _RESULT_CAT_RE.search(xml_text or "")
    if not match:
        return None
    code = int(match.group(1))
    category = match.group(2).strip()
    mapped = CDL_TO_CROP_ID.get(category.lower())
    return CdlCropYear(year=year, code=code, category=category, mapped_crop_id=mapped)


def detect_cdl_monoculture(history: List[CdlCropYear]) -> Optional[int]:
    """Count consecutive identical crop classifications from the most recent CDL year backwards."""
    valid = [item for item in sorted(history, key=lambda h: h.year, reverse=True) if item.mapped_crop_id]
    if not valid:
        return None
    latest = valid[0].mapped_crop_id
    streak = 0
    for item in valid:
        if item.mapped_crop_id == latest:
            streak += 1
        else:
            break
    return streak


def get_cdl_history(lat: float, lon: float, years: Tuple[int, ...] = (2024, 2023, 2022)) -> List[CdlCropYear]:
    """Fetch 3-year USDA NASS Cropland Data Layer history when coordinates fall inside continental USA."""
    if not is_conus_coordinate(lat, lon):
        return []

    cache_key = geo_cache.grid_key(lat, lon, step_deg=0.005, extra=",".join(map(str, years)))
    cached = geo_cache.get_json("usda_cdl", cache_key)
    if cached is not None:
        return [CdlCropYear.model_validate(item) for item in cached.get("items", [])]

    x, y = wgs84_to_epsg5070(lat, lon)
    items: List[CdlCropYear] = []
    any_error = False

    def _fetch_year(yr: int) -> Optional[CdlCropYear]:
        with httpx.Client(timeout=3.5) as client:
            resp = client.get(
                settings.usda_cdl_url,
                params={"year": yr, "x": x, "y": y},
            )
            resp.raise_for_status()
            return parse_cdl_xml(resp.text, year=yr)

    with ThreadPoolExecutor(max_workers=len(years)) as pool:
        futures = {pool.submit(_fetch_year, yr): yr for yr in years}
        for future, yr in futures.items():
            try:
                parsed = future.result()
                if parsed is not None:
                    items.append(parsed)
            except Exception as exc:
                any_error = True
                logger.debug("USDA CDL year %s failed (%s)", yr, exc)

    if items:
        geo_cache.set_json(
            "usda_cdl",
            cache_key,
            {"items": [i.model_dump() for i in items]},
            ttl_seconds=settings.cache_cdl_ttl_days * 86400,
        )
    elif any_error:
        # Short 15-min cooldown cache on transient network timeouts
        geo_cache.set_json("usda_cdl", cache_key, {"items": []}, ttl_seconds=900)

    return items
