from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import (
    AnnualClimatePoint,
    ClimateAnalysis,
    ClimateAnomalies,
    MonthlyClimatePoint,
    MonthlyClimatologyPoint,
    SoilProfile,
    TerrainAnalysis,
)

client = TestClient(app)


def _mock_climate(*args, **kwargs):
    return ClimateAnalysis(
        source="mock_nasa_power",
        hemisphere="Sur",
        anomalies=ClimateAnomalies(
            climate_zone="Templada (Sur)",
            seasonal_focus_label="Verano",
            baseline_period="2015-2022",
            recent_period="2023-2025",
            baseline_avg_temp_c=18.0,
            recent_avg_temp_c=19.1,
            temp_anomaly_c=1.1,
            summer_temp_anomaly_c=1.4,
            baseline_annual_rain_mm=780.0,
            recent_annual_rain_mm=630.0,
            rain_anomaly_pct=-19.2,
            summer_rain_anomaly_pct=-22.0,
            min_temp_coldest_month_c=6.5,
            avg_rh2m_pct=66.0,
            avg_soil_wetness_top=0.48,
            avg_soil_wetness_root=0.52,
            dry_soil_months=["Jul"],
            annual_et0_mm=980.0,
            water_balance_mm=-350.0,
            frost_risk_months=[],
            drier_recent_trend=True,
            hotter_recent_trend=True,
            frost_risk_present=False,
            high_humidity_risk=False,
            climate_alerts=["Veranos recientes +1.4 °C más cálidos y -22% de lluvias."],
        ),
        annual_series=[
            AnnualClimatePoint(
                year=2024,
                avg_temp_c=19.1,
                summer_avg_temp_c=25.4,
                total_rain_mm=630.0,
                summer_rain_mm=240.0,
                avg_soil_wetness_top=0.48,
                total_et0_mm=980.0,
            )
        ],
        recent_monthly_series=[
            MonthlyClimatePoint(period="2024-01", year=2024, month=1, temp_c=25.0, rain_mm=80.0)
        ],
        monthly_climatology=[
            MonthlyClimatologyPoint(
                month=m,
                month_name=f"M{m}",
                avg_temp_c=20.0,
                avg_temp_min_c=12.0,
                avg_rain_mm=60.0,
                avg_rh2m_pct=66.0,
                avg_soil_wetness_top=0.48,
                avg_et0_mm=82.0,
            )
            for m in range(1, 13)
        ],
    )


def _mock_terrain(*args, **kwargs):
    return TerrainAnalysis(
        elevation_m=259.0,
        min_elevation_m=255.0,
        max_elevation_m=265.0,
        slope_pct=3.2,
        max_slope_pct=4.1,
        slope_deg=1.83,
        terrain_class="Ondulado moderado",
        source="mock_srtm",
        erosion_risk="Moderado",
        area_ha=15.5,
        polygon_vertices=4,
    )


def _mock_soil(*args, **kwargs):
    return SoilProfile(
        ph_h2o=6.7,
        clay_pct=33.6,
        sand_pct=18.0,
        silt_pct=48.4,
        soc_g_kg=21.9,
        texture_class="Franco arcillo-limoso",
        drainage_class="Moderado / Equilibrado",
        ph_class="Neutro (óptimo agrícola)",
        source="mock_soilgrids",
    )


def test_health_and_crops_endpoints():
    health = client.get("/api/health")
    assert health.status_code == 200
    assert set(health.json()["channels"]) == {"web", "whatsapp", "mobile"}
    assert len(health.json()["pillars"]) == 5

    crops = client.get("/api/crops")
    assert crops.status_code == 200
    assert len(crops.json()) == 8


@patch("app.channels.base.get_climate_analysis", side_effect=_mock_climate)
@patch("app.channels.base.get_terrain_slope", side_effect=_mock_terrain)
@patch("app.channels.base.get_soil_profile", side_effect=_mock_soil)
def test_recommend_rotation_and_channels(mock_s, mock_t, mock_c):
    resp = client.post(
        "/api/recommend-rotation",
        json={
            "lat": -31.48,
            "lon": -63.55,
            "current_crop": "maiz",
            "years_same_crop": 3,
            "channel": "web",
            "polygon": [
                {"lat": -31.480, "lon": -63.550},
                {"lat": -31.484, "lon": -63.550},
                {"lat": -31.484, "lon": -63.554},
                {"lat": -31.480, "lon": -63.554},
            ],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["scenarios"]) == 3
    assert data["soil_profile"]["ph_h2o"] == 6.7
    assert data["vegetation_health"]["monoculture_years"] == 3
    assert data["scenarios"][0]["economics"]["estimated_margin_usd_ha"] != 0

    wa_resp = client.post(
        "/api/channels/whatsapp/webhook",
        json={"from_number": "whatsapp:+549351123456", "body": "rotacion maiz -31.48, -63.55"},
    )
    assert wa_resp.status_code == 200
    wa_data = wa_resp.json()
    assert "Humedad SMAP" in wa_data["reply_text"]
    assert "Margen est." in wa_data["reply_text"]

    mob_resp = client.post(
        "/api/channels/mobile/recommend",
        json={"lat": -31.48, "lon": -63.55, "current_crop": "maiz"},
    )
    assert mob_resp.status_code == 200
    mob_data = mob_resp.json()
    assert mob_data["summary_badges"]["smap_wetness_pct"] == 48
    assert len(mob_data["cards"]) == 3
