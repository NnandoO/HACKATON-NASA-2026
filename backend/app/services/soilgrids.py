import logging
from typing import Any, Dict, Optional

import httpx

from app.config import settings
from app.schemas import SoilProfile
from app.services.geo_cache import geo_cache

logger = logging.getLogger(__name__)


def classify_usda_texture(clay_pct: float, sand_pct: float, silt_pct: float) -> str:
    """Simplified USDA soil texture triangle classification."""
    if clay_pct >= 40.0:
        return "Arcilloso"
    if sand_pct >= 70.0 and clay_pct < 15.0:
        return "Arenoso"
    if clay_pct >= 27.0:
        if sand_pct <= 20.0:
            return "Franco arcillo-limoso"
        if sand_pct >= 45.0:
            return "Franco arcillo-arenoso"
        return "Franco arcilloso"
    if silt_pct >= 50.0:
        return "Franco limoso"
    if sand_pct >= 52.0:
        return "Franco arenoso"
    return "Franco (equilibrado)"


def classify_drainage(clay_pct: float, sand_pct: float) -> str:
    if clay_pct >= 38.0:
        return "Lento (riesgo de encharcamiento)"
    if sand_pct >= 60.0:
        return "Rápido (alta infiltración)"
    return "Moderado / Equilibrado"


def classify_soil_ph(ph: float) -> str:
    if ph < 5.5:
        return "Ácido (requiere encalado o cultivos tolerantes)"
    if ph < 6.2:
        return "Ligeramente ácido"
    if ph <= 7.4:
        return "Neutro (óptimo agrícola)"
    return "Alcalino"


def _extract_layer_mean(layers: list[Dict[str, Any]], prop_name: str) -> Optional[float]:
    for layer in layers:
        if layer.get("name") != prop_name:
            continue
        d_factor = float(layer.get("unit_measure", {}).get("d_factor") or 1.0)
        values = []
        for depth in layer.get("depths", []):
            mean_val = depth.get("values", {}).get("mean")
            if mean_val is not None:
                values.append(float(mean_val) / d_factor)
        if values:
            return sum(values) / len(values)
    return None


def _query_usda_ssurgo_mapunit(lat: float, lon: float) -> Optional[str]:
    """Query USDA SSURGO Soil Data Access when coordinates are inside continental USA."""
    if not (24.5 <= lat <= 49.5 and -125.0 <= lon <= -66.0):
        return None
    query = (
        "SELECT TOP 1 muname FROM mapunit WHERE mukey IN "
        f"(SELECT * FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('point({lon:.5f} {lat:.5f})'))"
    )
    try:
        with httpx.Client(timeout=6.0) as client:
            resp = client.post(
                settings.usda_sda_url,
                json={"format": "JSON", "query": query},
            )
            resp.raise_for_status()
            table = resp.json().get("Table", [])
            if table and table[0]:
                return str(table[0][0])
    except Exception as exc:
        logger.debug("USDA SSURGO query skipped/failed (%s)", exc)
    return None


def parse_soilgrids_response(
    payload: Dict[str, Any],
    source: str = "isric_soilgrids_v2",
    usda_mapunit: Optional[str] = None,
) -> SoilProfile:
    layers = payload.get("properties", {}).get("layers", [])
    ph = _extract_layer_mean(layers, "phh2o")
    clay = _extract_layer_mean(layers, "clay")
    sand = _extract_layer_mean(layers, "sand")
    soc = _extract_layer_mean(layers, "soc")

    if ph is None or clay is None or sand is None:
        raise ValueError("SoilGrids pixel sin datos (zona urbana o cuerpo de agua).")

    clay = max(0.0, min(100.0, clay))
    sand = max(0.0, min(100.0 - clay, sand))
    silt = max(0.0, 100.0 - clay - sand)
    soc_val = soc if soc is not None else 15.0

    return SoilProfile(
        ph_h2o=round(ph, 2),
        clay_pct=round(clay, 1),
        sand_pct=round(sand, 1),
        silt_pct=round(silt, 1),
        soc_g_kg=round(soc_val, 1),
        texture_class=classify_usda_texture(clay, sand, silt),
        drainage_class=classify_drainage(clay, sand),
        ph_class=classify_soil_ph(ph),
        usda_ssurgo_mapunit=usda_mapunit,
        source=source,
    )


def get_soil_profile(lat: float, lon: float) -> SoilProfile:
    """Query ISRIC SoilGrids v2.0 globally and USDA SSURGO inside USA, backed by SQLite cache."""
    cache_key = geo_cache.grid_key(lat, lon, step_deg=0.01)
    cached = geo_cache.get_json("soil_profile", cache_key)
    if cached is not None:
        soil = SoilProfile.model_validate(cached)
        if not soil.source.endswith("_cache"):
            soil.source = f"{soil.source}_cache"
        return soil

    usda_mapunit = _query_usda_ssurgo_mapunit(lat, lon)
    params = [
        ("lon", round(lon, 5)),
        ("lat", round(lat, 5)),
        ("property", "phh2o"),
        ("property", "clay"),
        ("property", "sand"),
        ("property", "soc"),
        ("depth", "0-5cm"),
        ("depth", "5-15cm"),
        ("value", "mean"),
    ]
    try:
        with httpx.Client(timeout=min(6.0, settings.http_timeout_seconds)) as client:
            response = client.get(
                settings.soilgrids_base_url,
                params=params,
                headers={"User-Agent": "AgroNASA/3.0"},
            )
            response.raise_for_status()
            payload = response.json()
        source = "isric_soilgrids_v2+usda_ssurgo" if usda_mapunit else "isric_soilgrids_v2"
        soil = parse_soilgrids_response(payload, source=source, usda_mapunit=usda_mapunit)
        geo_cache.set_json(
            "soil_profile",
            cache_key,
            soil.model_dump(),
            ttl_seconds=settings.cache_soil_ttl_days * 86400,
        )
        return soil
    except Exception as exc:
        logger.warning("SoilGrids unavailable or masked (%s); using regional soil fallback.", exc)
        is_tropical = abs(lat) < 23.5
        ph = 5.7 if is_tropical else 6.5
        clay = 30.0 if is_tropical else 26.0
        sand = 32.0 if is_tropical else 34.0
        silt = 100.0 - clay - sand
        soc = 22.0 if is_tropical else 19.0
        fallback_soil = SoilProfile(
            ph_h2o=ph,
            clay_pct=clay,
            sand_pct=sand,
            silt_pct=silt,
            soc_g_kg=soc,
            texture_class=classify_usda_texture(clay, sand, silt),
            drainage_class=classify_drainage(clay, sand),
            ph_class=classify_soil_ph(ph),
            usda_ssurgo_mapunit=usda_mapunit,
            source="usda_ssurgo+fallback" if usda_mapunit else "fallback_soil_estimate",
        )
        # Cache fallback briefly (15 min) to avoid repeated timeout stalls on retries
        geo_cache.set_json("soil_profile", cache_key, fallback_soil.model_dump(), ttl_seconds=900)
        return fallback_soil
