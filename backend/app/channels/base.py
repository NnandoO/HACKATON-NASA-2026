from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from app.schemas import ChannelType, LatLonPoint, RecommendationResponse
from app.services.crop_catalog import CropCatalog
from app.services.market_economics import MarketEconomicsService
from app.services.nasa_power import get_climate_analysis
from app.services.rotation_engine import generate_rotation_scenarios
from app.services.soilgrids import get_soil_profile
from app.services.srtm_elevation import (
    calculate_polygon_centroid_and_area_ha,
    get_terrain_slope,
)
from app.services.usda_cdl import get_cdl_history
from app.services.vegetation_ndvi import _fetch_ornl_modis_ndvi, analyze_vegetation_health


class RecommendationOrchestrator:
    """Channel-agnostic core service powering Web, WhatsApp, and Mobile App."""

    def __init__(
        self,
        catalog: CropCatalog | None = None,
        economics: MarketEconomicsService | None = None,
    ) -> None:
        self.catalog = catalog or CropCatalog()
        self.economics = economics or MarketEconomicsService()

    def recommend(
        self,
        lat: float,
        lon: float,
        current_crop_query: str,
        channel: ChannelType = ChannelType.WEB,
        polygon: Optional[List[LatLonPoint]] = None,
        years_same_crop: int = 1,
    ) -> RecommendationResponse:
        current_crop = self.catalog.resolve(current_crop_query)
        if current_crop is None:
            available = ", ".join(c.name for c in self.catalog.list_crops())
            raise ValueError(
                f"Cultivo '{current_crop_query}' no reconocido. Cultivos disponibles: {available}."
            )

        target_lat, target_lon = lat, lon
        if polygon and len(polygon) >= 3:
            target_lat, target_lon, _ = calculate_polygon_centroid_and_area_ha(polygon)

        if abs(target_lat) > 68.0:
            raise ValueError(
                "Coordenadas en zona polar (>68° de latitud): fuera de la frontera agrícola mundial. "
                "Seleccioná una parcela en zona cultivable."
            )

        terrain = get_terrain_slope(target_lat, target_lon, polygon)
        if getattr(terrain, "is_ocean", False):
            raise ValueError(
                "Las coordenadas seleccionadas caen sobre océano o cuerpo de agua sin suelo cultivable. "
                "Mové el marcador a tierra firme."
            )

        with ThreadPoolExecutor(max_workers=4) as pool:
            climate_future = pool.submit(get_climate_analysis, target_lat, target_lon)
            soil_future = pool.submit(get_soil_profile, target_lat, target_lon)
            ndvi_future = pool.submit(_fetch_ornl_modis_ndvi, target_lat, target_lon)
            cdl_future = pool.submit(get_cdl_history, target_lat, target_lon)
            climate = climate_future.result()
            soil = soil_future.result()
            prefetched_ndvi = ndvi_future.result()
            prefetched_cdl = cdl_future.result()

        if (
            climate.anomalies.recent_annual_rain_mm < 100.0
            and climate.anomalies.avg_soil_wetness_root < 0.22
        ):
            desert_msg = (
                "Zona hiperárida (<100 mm/año y humedad radicular crítica): "
                "sin riego tecnificado o invernadero la agricultura de secano es inviable."
            )
            if desert_msg not in climate.anomalies.climate_alerts:
                climate.anomalies.climate_alerts.insert(0, desert_msg)

        vegetation = analyze_vegetation_health(
            climate=climate,
            current_crop=current_crop,
            years_same_crop=years_same_crop,
            lat=target_lat,
            lon=target_lon,
            prefetched_ndvi=prefetched_ndvi,
            prefetched_cdl=prefetched_cdl,
        )

        effective_years = max(years_same_crop, vegetation.auto_detected_monoculture_years or 1)

        scenarios = generate_rotation_scenarios(
            current_crop=current_crop,
            catalog=self.catalog,
            climate=climate,
            terrain=terrain,
            soil=soil,
            economics_svc=self.economics,
            years_same_crop=effective_years,
        )

        provenance = {
            "climate": climate.source,
            "terrain": terrain.source,
            "soil": soil.source,
            "vegetation": vegetation.source,
            "market": "usda_ams_nass_reference",
            "cache_hits": sum(1 for src in (climate.source, terrain.source, soil.source) if "cache" in src),
        }

        return RecommendationResponse(
            channel=channel,
            location={"lat": round(target_lat, 5), "lon": round(target_lon, 5)},
            current_crop=current_crop,
            climate_analysis=climate,
            terrain_analysis=terrain,
            soil_profile=soil,
            vegetation_health=vegetation,
            scenarios=scenarios,
            data_provenance=provenance,
        )
