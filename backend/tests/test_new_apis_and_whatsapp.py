from unittest.mock import patch
from fastapi.testclient import TestClient

from app.channels.base import RecommendationOrchestrator
from app.channels.whatsapp_adapter import handle_whatsapp_query
from app.main import app
from app.schemas import CdlCropYear, WhatsAppIncomingMessage
from app.services import nasa_power, usda_cdl, vegetation_ndvi
from app.services.geo_cache import GeoSQLiteCache


def test_usda_cdl_projection_and_monoculture_detection():
    x, y = usda_cdl.wgs84_to_epsg5070(41.9, -93.6)
    assert 190000 < x < 210000
    assert 2090000 < y < 2130000

    xml_sample = '<ns1:GetCDLValueResponse><Result>{x: 198688.0, y: 2116440.0, value: 1, category: "Corn", color: "#FFD300"}</Result></ns1:GetCDLValueResponse>'
    parsed = usda_cdl.parse_cdl_xml(xml_sample, year=2024)
    assert parsed is not None
    assert parsed.code == 1
    assert parsed.category == "Corn"
    assert parsed.mapped_crop_id == "maiz"

    history = [
        CdlCropYear(year=2024, code=1, category="Corn", mapped_crop_id="maiz"),
        CdlCropYear(year=2023, code=1, category="Corn", mapped_crop_id="maiz"),
        CdlCropYear(year=2022, code=1, category="Corn", mapped_crop_id="maiz"),
    ]
    assert usda_cdl.detect_cdl_monoculture(history) == 3


def test_nasa_power_daily_storm_detection(tmp_path, monkeypatch):
    cache = GeoSQLiteCache(str(tmp_path / "daily.sqlite3"))
    monkeypatch.setattr(nasa_power, "geo_cache", cache)

    fake_daily = {
        "properties": {
            "parameter": {
                "PRECTOTCORR": {
                    "20250101": 5.0,
                    "20250102": 48.5,
                    "20250103": 42.0,
                    "20250104": 55.2,
                    "20250105": 28.0,
                }
            }
        }
    }
    with patch.object(nasa_power, "fetch_nasa_power_daily_raw", return_value=fake_daily):
        metrics = nasa_power.get_daily_storm_metrics(-31.48, -63.55, end_year=2025)
        assert metrics["extreme_rain_days_gt40mm"] == 3
        assert metrics["heavy_rain_days_gt25mm"] == 4
        assert metrics["max_daily_rain_mm"] == 55.2


def test_vegetation_ndvi_series_fallback_and_cdl_alert(tmp_path, monkeypatch):
    cache = GeoSQLiteCache(str(tmp_path / "veg.sqlite3"))
    monkeypatch.setattr(vegetation_ndvi, "geo_cache", cache)
    monkeypatch.setattr(usda_cdl, "geo_cache", cache)

    raw = nasa_power._build_fallback_raw(lat=41.9, start_year=2015, end_year=2025)
    climate = nasa_power.parse_nasa_power_with_pandas(raw, lat=41.9)
    orch = RecommendationOrchestrator()
    corn = orch.catalog.resolve("maiz")

    cdl_hist = [
        CdlCropYear(year=2024, code=1, category="Corn", mapped_crop_id="maiz"),
        CdlCropYear(year=2023, code=1, category="Corn", mapped_crop_id="maiz"),
        CdlCropYear(year=2022, code=1, category="Corn", mapped_crop_id="maiz"),
    ]
    with patch.object(vegetation_ndvi, "_fetch_ornl_modis_ndvi", return_value=[]):
        with patch.object(vegetation_ndvi, "get_cdl_history", return_value=cdl_hist):
            veg = vegetation_ndvi.analyze_vegetation_health(
                climate=climate,
                current_crop=corn,
                years_same_crop=1,
                lat=41.9,
                lon=-93.6,
            )
            assert len(veg.ndvi_series) == 12
            assert veg.auto_detected_monoculture_years == 3
            assert veg.monoculture_years == 3
            assert veg.soil_exhaustion_risk == "Alto"
            assert "USDA CDL" in veg.vegetation_alert


def test_whatsapp_two_step_conversation_and_twilio_twiml(tmp_path, monkeypatch):
    from app.channels import whatsapp_adapter

    wa_cache = GeoSQLiteCache(str(tmp_path / "wa.sqlite3"))
    monkeypatch.setattr(whatsapp_adapter, "geo_cache", wa_cache)

    orch = RecommendationOrchestrator()
    phone = "whatsapp:+549351123456"

    # Step 1: user sends GPS coordinates only
    out1, rec1 = handle_whatsapp_query(
        WhatsAppIncomingMessage(from_number=phone, body="", latitude=-31.48, longitude=-63.55),
        orch,
    )
    assert rec1 is None
    assert out1.parsed_intent["step"] == "awaiting_crop"
    assert "1) Maíz" in out1.reply_text

    # Step 2: user replies "1 3 años"
    raw = nasa_power._build_fallback_raw(lat=-31.48, start_year=2015, end_year=2025)
    climate = nasa_power.parse_nasa_power_with_pandas(raw, lat=-31.48)
    with patch("app.channels.base.get_climate_analysis", return_value=climate):
        with patch("app.channels.base.get_terrain_slope") as mock_t:
            from app.schemas import TerrainAnalysis, SoilProfile

            mock_t.return_value = TerrainAnalysis(
                elevation_m=250.0,
                min_elevation_m=248.0,
                max_elevation_m=253.0,
                slope_pct=2.5,
                max_slope_pct=3.0,
                slope_deg=1.4,
                terrain_class="Plano / Suave",
                source="mock_srtm",
                erosion_risk="Bajo",
            )
            with patch("app.channels.base.get_soil_profile") as mock_s:
                mock_s.return_value = SoilProfile(
                    ph_h2o=6.5,
                    clay_pct=26.0,
                    sand_pct=34.0,
                    silt_pct=40.0,
                    soc_g_kg=19.0,
                    texture_class="Franco (equilibrado)",
                    drainage_class="Moderado / Equilibrado",
                    ph_class="Neutro (óptimo agrícola)",
                    source="mock_soil",
                )
                with patch.object(vegetation_ndvi, "_fetch_ornl_modis_ndvi", return_value=[]):
                    out2, rec2 = handle_whatsapp_query(
                        WhatsAppIncomingMessage(from_number=phone, body="1 3 años"),
                        orch,
                    )
                    assert rec2 is not None
                    assert rec2.current_crop.id == "maiz"
                    assert rec2.vegetation_health.monoculture_years == 3
                    assert out2.parsed_intent["step"] == "completed"

                    # Verify Twilio TwiML endpoint
                    client = TestClient(app)
                    twilio_resp = client.post(
                        "/api/channels/whatsapp/twilio",
                        data={"From": phone, "Body": "ayuda"},
                    )
                    assert twilio_resp.status_code == 200
                    assert "application/xml" in twilio_resp.headers["content-type"]
                    assert "<Response><Message>" in twilio_resp.text
