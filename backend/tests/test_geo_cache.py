from unittest.mock import patch
import pytest

from app.channels.base import RecommendationOrchestrator
from app.services import nasa_power, soilgrids, srtm_elevation
from app.services.geo_cache import GeoSQLiteCache


def test_geo_sqlite_cache_roundtrip_and_grid_key(tmp_path):
    cache = GeoSQLiteCache(str(tmp_path / "cache.sqlite3"))
    key = cache.grid_key(-31.484, -63.553, step_deg=0.01)
    assert key == "-31.4800,-63.5500"

    assert cache.get_json("srtm_terrain", key) is None
    cache.set_json("srtm_terrain", key, {"elevation_m": 259.0}, ttl_seconds=3600)
    assert cache.get_json("srtm_terrain", key) == {"elevation_m": 259.0}

    stats = cache.stats()
    assert stats["active_entries"] == 1
    assert stats["by_namespace"]["srtm_terrain"] == 1


def test_polar_coordinates_rejected_immediately():
    orch = RecommendationOrchestrator()
    with pytest.raises(ValueError, match="zona polar"):
        orch.recommend(lat=75.0, lon=15.0, current_crop_query="maiz")


def test_ocean_coordinates_detected_by_srtm_and_cached(tmp_path, monkeypatch):
    test_cache = GeoSQLiteCache(str(tmp_path / "ocean_cache.sqlite3"))
    monkeypatch.setattr(srtm_elevation, "geo_cache", test_cache)

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"results": [{"elevation": None} for _ in range(5)]}

    call_count = {"n": 0}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, *args, **kwargs):
            call_count["n"] += 1
            return FakeResp()

    with patch.object(srtm_elevation.httpx, "Client", FakeClient):
        terrain_first = srtm_elevation.get_terrain_slope(0.0, -30.0)
        assert terrain_first.is_ocean is True
        assert call_count["n"] == 1

        terrain_second = srtm_elevation.get_terrain_slope(0.001, -30.001)
        assert terrain_second.is_ocean is True
        assert terrain_second.source.endswith("_cache")
        assert call_count["n"] == 1  # served from SQLite cache without HTTP call

    orch = RecommendationOrchestrator()
    with patch("app.channels.base.get_terrain_slope", return_value=terrain_second):
        with pytest.raises(ValueError, match="océano"):
            orch.recommend(lat=0.0, lon=-30.0, current_crop_query="maiz")


def test_nasa_power_and_soil_use_cache_on_repeat(tmp_path, monkeypatch):
    test_cache = GeoSQLiteCache(str(tmp_path / "climate_soil.sqlite3"))
    monkeypatch.setattr(nasa_power, "geo_cache", test_cache)
    monkeypatch.setattr(soilgrids, "geo_cache", test_cache)

    sample_raw = nasa_power._build_fallback_raw(lat=-31.48, start_year=2015, end_year=2025)
    with patch.object(nasa_power, "fetch_nasa_power_raw", return_value=sample_raw) as mock_fetch:
        c1 = nasa_power.get_climate_analysis(-31.48, -63.55)
        c2 = nasa_power.get_climate_analysis(-31.49, -63.54)
        assert c1.source == "nasa_power_api"
        assert c2.source == "nasa_power_api_cache"
        assert mock_fetch.call_count == 1
