import logging
import math
from typing import List, Optional, Tuple

import httpx

from app.config import settings
from app.schemas import LatLonPoint, TerrainAnalysis
from app.services.geo_cache import geo_cache

logger = logging.getLogger(__name__)

METERS_OFFSET = 90.0
EARTH_RADIUS_M = 6_378_137.0


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def calculate_polygon_centroid_and_area_ha(polygon: List[LatLonPoint]) -> Tuple[float, float, float]:
    """Compute centroid (lat, lon) and planar projected area in hectares for a parcel polygon."""
    if len(polygon) < 3:
        raise ValueError("El polígono requiere al menos 3 vértices.")

    avg_lat = sum(p.lat for p in polygon) / len(polygon)
    avg_lon = sum(p.lon for p in polygon) / len(polygon)
    cos_lat = max(0.1, math.cos(math.radians(avg_lat)))
    meters_per_deg_lat = (math.pi / 180.0) * EARTH_RADIUS_M
    meters_per_deg_lon = meters_per_deg_lat * cos_lat

    coords_m = [
        ((p.lon - avg_lon) * meters_per_deg_lon, (p.lat - avg_lat) * meters_per_deg_lat)
        for p in polygon
    ]

    area_m2_twice = 0.0
    n = len(coords_m)
    for i in range(n):
        x1, y1 = coords_m[i]
        x2, y2 = coords_m[(i + 1) % n]
        area_m2_twice += x1 * y2 - x2 * y1

    area_ha = abs(area_m2_twice) / 2.0 / 10_000.0
    return avg_lat, avg_lon, round(area_ha, 2)


def _build_5_point_stencil(lat: float, lon: float) -> Tuple[List[Tuple[float, float]], float, float]:
    d_lat = math.degrees(METERS_OFFSET / EARTH_RADIUS_M)
    cos_lat = max(0.1, math.cos(math.radians(lat)))
    d_lon = math.degrees(METERS_OFFSET / (EARTH_RADIUS_M * cos_lat))

    points = [
        (lat, lon),
        (lat + d_lat, lon),
        (lat - d_lat, lon),
        (lat, lon + d_lon),
        (lat, lon - d_lon),
    ]
    return points, 2.0 * METERS_OFFSET, 2.0 * METERS_OFFSET


def _classify_slope(slope_pct: float) -> Tuple[str, str]:
    if slope_pct < 3.0:
        return "Plano / Suave", "Bajo"
    if slope_pct < 8.0:
        return "Ondulado moderado", "Moderado"
    if slope_pct < 15.0:
        return "Inclinado / Ladera", "Alto"
    return "Escarpado", "Crítico"


def calculate_slope_from_elevations(
    elevations: List[float],
    dx_m: float,
    dy_m: float,
    source: str = "nasa_srtm_90m_opentopodata",
    polygon_points: Optional[List[Tuple[float, float]]] = None,
    polygon_elevations: Optional[List[float]] = None,
    area_ha: Optional[float] = None,
) -> TerrainAnalysis:
    """Compute terrain slope percentage, degrees, and optional polygon relief metrics."""
    if len(elevations) < 5:
        raise ValueError("Expected 5 elevation samples (center, N, S, E, W).")

    center, north, south, east, west = [float(e) for e in elevations[:5]]
    dz_dy = (north - south) / dy_m
    dz_dx = (east - west) / dx_m
    gradient = math.sqrt(dz_dx ** 2 + dz_dy ** 2)

    center_slope_pct = round(gradient * 100.0, 2)
    max_slope_pct = center_slope_pct
    all_elevs = [center, north, south, east, west]

    if polygon_points and polygon_elevations and len(polygon_points) == len(polygon_elevations):
        all_elevs.extend(polygon_elevations)
        n = len(polygon_points)
        for i in range(n):
            j = (i + 1) % n
            dist = haversine_distance_m(
                polygon_points[i][0],
                polygon_points[i][1],
                polygon_points[j][0],
                polygon_points[j][1],
            )
            if dist > 15.0:
                edge_slope = abs(polygon_elevations[i] - polygon_elevations[j]) / dist * 100.0
                max_slope_pct = max(max_slope_pct, round(edge_slope, 2))

    slope_for_risk = round((center_slope_pct + max_slope_pct) / 2.0, 2) if polygon_points else center_slope_pct
    slope_deg = round(math.degrees(math.atan(slope_for_risk / 100.0)), 2)
    terrain_class, erosion_risk = _classify_slope(slope_for_risk)

    return TerrainAnalysis(
        elevation_m=round(center, 1),
        min_elevation_m=round(min(all_elevs), 1),
        max_elevation_m=round(max(all_elevs), 1),
        slope_pct=slope_for_risk,
        max_slope_pct=max_slope_pct,
        slope_deg=slope_deg,
        terrain_class=terrain_class,
        source=source,
        erosion_risk=erosion_risk,
        area_ha=area_ha,
        polygon_vertices=len(polygon_points) if polygon_points else 0,
    )


def get_terrain_slope(
    lat: float,
    lon: float,
    polygon: Optional[List[LatLonPoint]] = None,
) -> TerrainAnalysis:
    """Query NASA SRTM 90m elevation via OpenTopoData (with SQLite cache & ocean screening)."""
    area_ha: Optional[float] = None
    poly_tuples: Optional[List[Tuple[float, float]]] = None
    poly_sig = ""

    if polygon and len(polygon) >= 3:
        lat, lon, area_ha = calculate_polygon_centroid_and_area_ha(polygon)
        poly_tuples = [(p.lat, p.lon) for p in polygon[:25]]
        poly_sig = f"poly:{len(poly_tuples)}:{area_ha}"

    cache_key = geo_cache.grid_key(lat, lon, step_deg=0.01, extra=poly_sig)
    cached = geo_cache.get_json("srtm_terrain", cache_key)
    if cached is not None:
        terrain = TerrainAnalysis.model_validate(cached)
        if not terrain.source.endswith("_cache"):
            terrain.source = f"{terrain.source}_cache"
        return terrain

    stencil_points, dx_m, dy_m = _build_5_point_stencil(lat, lon)
    all_points = list(stencil_points) + (poly_tuples or [])
    locations_param = "|".join(f"{p_lat:.6f},{p_lon:.6f}" for p_lat, p_lon in all_points)

    try:
        with httpx.Client(timeout=settings.http_timeout_seconds) as client:
            response = client.get(
                settings.srtm_base_url,
                params={"locations": locations_param},
            )
            response.raise_for_status()
            payload = response.json()

        results = payload.get("results", [])
        raw_elevs = [item.get("elevation") for item in results]
        if len(raw_elevs) < 5:
            raise ValueError("Incomplete SRTM response")

        # Within SRTM global coverage (-59.5..59.5), all-null stencil elevations indicate ocean/water body
        if abs(lat) <= 59.5 and all(val is None for val in raw_elevs[:5]):
            ocean_terrain = TerrainAnalysis(
                elevation_m=0.0,
                min_elevation_m=0.0,
                max_elevation_m=0.0,
                slope_pct=0.0,
                max_slope_pct=0.0,
                slope_deg=0.0,
                terrain_class="Océano / Cuerpo de agua",
                source="nasa_srtm_90m_opentopodata_ocean",
                erosion_risk="No aplica",
                area_ha=area_ha,
                polygon_vertices=len(poly_tuples) if poly_tuples else 0,
                is_ocean=True,
            )
            geo_cache.set_json(
                "srtm_terrain",
                cache_key,
                ocean_terrain.model_dump(),
                ttl_seconds=settings.cache_terrain_ttl_days * 86400,
            )
            return ocean_terrain

        elevations = [float(val) if val is not None else 0.0 for val in raw_elevs]
        stencil_elevs = elevations[:5]
        poly_elevs = elevations[5:] if poly_tuples else None

        terrain = calculate_slope_from_elevations(
            elevations=stencil_elevs,
            dx_m=dx_m,
            dy_m=dy_m,
            source="nasa_srtm_90m_opentopodata",
            polygon_points=poly_tuples,
            polygon_elevations=poly_elevs,
            area_ha=area_ha,
        )
        geo_cache.set_json(
            "srtm_terrain",
            cache_key,
            terrain.model_dump(),
            ttl_seconds=settings.cache_terrain_ttl_days * 86400,
        )
        return terrain
    except Exception as exc:
        logger.warning("SRTM elevation API unavailable (%s); using fallback terrain estimate.", exc)
        pseudo_elev = round(120.0 + abs(lat) * 4.5, 1)
        pseudo_slope = round(1.8 + (abs(lat * 10 + lon * 10) % 4.5), 2)
        gradient = pseudo_slope / 100.0
        terrain_class, erosion_risk = _classify_slope(pseudo_slope)
        return TerrainAnalysis(
            elevation_m=pseudo_elev,
            min_elevation_m=round(pseudo_elev - 2.0, 1),
            max_elevation_m=round(pseudo_elev + 2.5, 1),
            slope_pct=pseudo_slope,
            max_slope_pct=round(pseudo_slope * 1.2, 2),
            slope_deg=round(math.degrees(math.atan(gradient)), 2),
            terrain_class=terrain_class,
            source="fallback_offline_estimate",
            erosion_risk=erosion_risk,
            area_ha=area_ha,
            polygon_vertices=len(poly_tuples) if poly_tuples else 0,
            is_ocean=False,
        )
