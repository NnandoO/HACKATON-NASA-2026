from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AgroNASA - Motor de Rotación de Cultivos"
    app_version: str = "3.0.0"
    fao_rules_path: str = str(
        Path(__file__).resolve().parents[2] / "data" / "fao_crops_rules.json"
    )
    market_prices_path: str = str(
        Path(__file__).resolve().parents[2] / "data" / "market_prices_reference.json"
    )
    nasa_power_base_url: str = "https://power.larc.nasa.gov/api/temporal/monthly/point"
    srtm_base_url: str = "https://api.opentopodata.org/v1/srtm90m"
    soilgrids_base_url: str = "https://rest.isric.org/soilgrids/v2.0/properties/query"
    usda_sda_url: str = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"
    nasa_gibs_ndvi_wmts: str = (
        "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/"
        "MODIS_Terra_NDVI_8Day/default/2025-10-16/"
        "GoogleMapsCompatible_Level9/{z}/{y}/{x}.png"
    )
    http_timeout_seconds: float = 15.0
    geo_cache_db_path: str = str(
        Path(__file__).resolve().parents[2] / "data" / "agro_geo_cache.sqlite3"
    )
    cache_climate_ttl_hours: int = 24
    cache_terrain_ttl_days: int = 30
    cache_soil_ttl_days: int = 30
    cors_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)


settings = Settings()
