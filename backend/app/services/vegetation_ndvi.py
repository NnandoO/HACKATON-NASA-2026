import logging
from typing import List, Optional

import httpx

from app.config import settings
from app.schemas import CdlCropYear, ClimateAnalysis, CropRule, NdviHistoryPoint, VegetationHealth
from app.services.geo_cache import geo_cache
from app.services.usda_cdl import detect_cdl_monoculture, get_cdl_history

logger = logging.getLogger(__name__)


def _fetch_ornl_modis_ndvi(lat: float, lon: float) -> List[NdviHistoryPoint]:
    """Query ORNL DAAC MODIS MOD13Q1 250m 16-day NDVI time series with 7-day SQLite cache."""
    cache_key = geo_cache.grid_key(lat, lon, step_deg=0.01)
    cached = geo_cache.get_json("ornl_modis_ndvi", cache_key)
    if cached is not None:
        return [NdviHistoryPoint.model_validate(pt) for pt in cached.get("series", [])]

    series: List[NdviHistoryPoint] = []
    try:
        with httpx.Client(timeout=3.0, headers={"Accept": "application/json"}) as client:
            dates_resp = client.get(
                f"{settings.ornl_modis_base_url}/dates",
                params={"latitude": round(lat, 5), "longitude": round(lon, 5)},
            )
            dates_resp.raise_for_status()
            all_dates = dates_resp.json().get("dates", [])
            if len(all_dates) >= 2:
                window = all_dates[-12:]
                sub_resp = client.get(
                    f"{settings.ornl_modis_base_url}/subset",
                    params={
                        "latitude": round(lat, 5),
                        "longitude": round(lon, 5),
                        "band": "250m_16_days_NDVI",
                        "startDate": window[0]["modis_date"],
                        "endDate": window[-1]["modis_date"],
                        "kmAboveBelow": 0,
                        "kmLeftRight": 0,
                    },
                )
                sub_resp.raise_for_status()
                payload = sub_resp.json()
                scale = float(payload.get("scale") or 0.0001)
                for row in payload.get("subset", []):
                    raw_vals = [v for v in (row.get("data") or []) if isinstance(v, (int, float)) and v > -3000]
                    if raw_vals:
                        ndvi_val = round(max(0.0, min(0.95, (sum(raw_vals) / len(raw_vals)) * scale)), 2)
                        series.append(
                            NdviHistoryPoint(
                                date=str(row.get("calendar_date", row.get("modis_date", ""))),
                                ndvi=ndvi_val,
                                source="nasa_ornl_modis_13q1",
                            )
                        )
        if series:
            geo_cache.set_json(
                "ornl_modis_ndvi",
                cache_key,
                {"series": [s.model_dump() for s in series]},
                ttl_seconds=settings.cache_ndvi_ttl_days * 86400,
            )
            return series
    except Exception as exc:
        logger.debug("ORNL MODIS MOD13Q1 unavailable (%s); falling back to SMAP/GIBS NDVI model.", exc)

    # Brief 15-min cooldown cache so repeated requests don't stall on ORNL timeouts
    geo_cache.set_json("ornl_modis_ndvi", cache_key, {"series": []}, ttl_seconds=900)
    return []


def _build_power_ndvi_series(climate: ClimateAnalysis) -> List[NdviHistoryPoint]:
    series: List[NdviHistoryPoint] = []
    for pt in climate.recent_monthly_series[-12:]:
        wet = pt.soil_wetness_root if pt.soil_wetness_root is not None else 0.45
        rain_fac = min(1.0, pt.rain_mm / 120.0)
        ndvi = round(max(0.18, min(0.86, 0.28 + 0.36 * wet + 0.18 * rain_fac)), 2)
        series.append(
            NdviHistoryPoint(
                date=pt.period,
                ndvi=ndvi,
                source="power_smap_moisture_proxy",
            )
        )
    return series


def analyze_vegetation_health(
    climate: ClimateAnalysis,
    current_crop: CropRule,
    years_same_crop: int = 1,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    prefetched_ndvi: Optional[List[NdviHistoryPoint]] = None,
    prefetched_cdl: Optional[List[CdlCropYear]] = None,
) -> VegetationHealth:
    """Combine MODIS NDVI time series (or SMAP proxy) and USDA CDL monoculture auto-detection."""
    anomalies = climate.anomalies
    real_series = (
        prefetched_ndvi
        if prefetched_ndvi is not None
        else (_fetch_ornl_modis_ndvi(lat, lon) if lat is not None and lon is not None else [])
    )
    cdl_history = (
        prefetched_cdl
        if prefetched_cdl is not None
        else (get_cdl_history(lat, lon) if lat is not None and lon is not None else [])
    )
    auto_streak = detect_cdl_monoculture(cdl_history) if cdl_history else None

    if real_series:
        ndvi_series = real_series
        estimated_ndvi = real_series[-1].ndvi
        source = "nasa_ornl_modis_13q1"
    else:
        ndvi_series = _build_power_ndvi_series(climate)
        wet_root = anomalies.avg_soil_wetness_root
        rain_factor = min(1.0, anomalies.recent_annual_rain_mm / 900.0)
        raw_ndvi = 0.30 + 0.35 * wet_root + 0.20 * rain_factor
        if anomalies.drier_recent_trend and anomalies.hotter_recent_trend:
            raw_ndvi -= 0.08
        estimated_ndvi = round(max(0.22, min(0.86, raw_ndvi)), 2)
        source = "nasa_gibs_modis_ndvi+power_moisture_model"

    if cdl_history:
        source = f"{source}+usda_cdl"

    if estimated_ndvi >= 0.62:
        ndvi_status = "Vigor alto (buena cobertura vegetal)"
    elif estimated_ndvi >= 0.45:
        ndvi_status = "Vigor moderado (estrés estacional leve)"
    else:
        ndvi_status = "Vigor bajo (estrés hídrico / cobertura escasa)"

    effective_years = max(years_same_crop, auto_streak or 1)
    cdl_note = ""
    if cdl_history and auto_streak is not None and auto_streak >= 2:
        cdl_summary = " → ".join(f"{h.year}: {h.category}" for h in sorted(cdl_history, key=lambda x: x.year))
        cdl_note = f" (USDA CDL detectó historial: {cdl_summary})."

    if effective_years >= 3:
        exhaustion = "Alto"
        alert = (
            f"Monocultivo detectado: {effective_years} años seguidos con patrón similar a {current_crop.name}{cdl_note} "
            "Riesgo elevado de agotamiento nutricional y acumulación de patógenos; rotación urgente recomendada."
        )
    elif effective_years == 2:
        exhaustion = "Moderado"
        alert = (
            f"Llevas {effective_years} campañas consecutivas de {current_crop.name}{cdl_note} "
            "Conviene cambiar de familia botánica en el próximo ciclo para evitar caída de rendimiento."
        )
    else:
        exhaustion = "Bajo"
        alert = (
            f"Rotación preventiva tras {current_crop.name}: momento óptimo para alternar familia botánica y mantener vigor NDVI.{cdl_note}"
        )

    return VegetationHealth(
        estimated_ndvi=estimated_ndvi,
        ndvi_status=ndvi_status,
        ndvi_layer_url=settings.nasa_gibs_ndvi_wmts,
        monoculture_years=effective_years,
        soil_exhaustion_risk=exhaustion,
        vegetation_alert=alert,
        source=source,
        ndvi_series=ndvi_series,
        cdl_history=cdl_history,
        auto_detected_monoculture_years=auto_streak,
    )
