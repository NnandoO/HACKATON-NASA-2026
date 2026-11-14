from app.schemas import (
    AnnualClimatePoint,
    ClimateAnalysis,
    ClimateAnomalies,
    MonthlyClimatePoint,
    MonthlyClimatologyPoint,
    SoilProfile,
    TerrainAnalysis,
)
from app.services.crop_catalog import CropCatalog
from app.services.rotation_engine import generate_rotation_scenarios
from app.services.vegetation_ndvi import analyze_vegetation_health


def _sample_climate(rain_mm: float = 480.0, temp_c: float = 22.0, drier: bool = True) -> ClimateAnalysis:
    climatology = [
        MonthlyClimatologyPoint(
            month=m,
            month_name=f"M{m}",
            avg_temp_c=temp_c,
            avg_temp_min_c=10.0,
            avg_rain_mm=80.0 if m in (3, 4, 10, 11) else 25.0,
            avg_rh2m_pct=68.0,
            avg_soil_wetness_top=0.52,
            avg_et0_mm=90.0,
        )
        for m in range(1, 13)
    ]
    return ClimateAnalysis(
        source="test",
        hemisphere="Sur",
        anomalies=ClimateAnomalies(
            climate_zone="Templada (Sur)",
            seasonal_focus_label="Verano",
            baseline_period="2015-2022",
            recent_period="2023-2025",
            baseline_avg_temp_c=temp_c - 1.0,
            recent_avg_temp_c=temp_c,
            temp_anomaly_c=1.0,
            summer_temp_anomaly_c=1.3,
            baseline_annual_rain_mm=rain_mm * 1.2,
            recent_annual_rain_mm=rain_mm,
            rain_anomaly_pct=-16.7 if drier else 0.0,
            summer_rain_anomaly_pct=-20.0 if drier else 0.0,
            min_temp_coldest_month_c=7.0,
            avg_rh2m_pct=68.0,
            avg_soil_wetness_top=0.43,
            avg_soil_wetness_root=0.48,
            dry_soil_months=["Jul", "Ago"],
            annual_et0_mm=1050.0,
            water_balance_mm=rain_mm - 1050.0,
            frost_risk_months=[],
            drier_recent_trend=drier,
            hotter_recent_trend=True,
            frost_risk_present=False,
            high_humidity_risk=False,
            climate_alerts=["Veranos recientes más secos y calurosos."],
        ),
        annual_series=[
            AnnualClimatePoint(
                year=2024,
                avg_temp_c=temp_c,
                summer_avg_temp_c=temp_c + 4.0,
                total_rain_mm=rain_mm,
                summer_rain_mm=rain_mm * 0.4,
                avg_soil_wetness_top=0.43,
                total_et0_mm=1050.0,
            )
        ],
        recent_monthly_series=[
            MonthlyClimatePoint(period="2024-01", year=2024, month=1, temp_c=temp_c, rain_mm=50.0)
        ],
        monthly_climatology=climatology,
    )


def test_rotation_engine_returns_three_scenarios_with_economics_and_monoculture():
    catalog = CropCatalog()
    maiz = catalog.resolve("maiz")
    assert maiz is not None

    climate = _sample_climate(rain_mm=460.0, temp_c=21.5, drier=True)
    terrain = TerrainAnalysis(
        elevation_m=280.0,
        min_elevation_m=275.0,
        max_elevation_m=292.0,
        slope_pct=9.5,
        max_slope_pct=11.0,
        slope_deg=5.4,
        terrain_class="Inclinado / Ladera",
        source="test",
        erosion_risk="Alto",
        area_ha=12.4,
        polygon_vertices=4,
    )
    soil = SoilProfile(
        ph_h2o=6.5,
        clay_pct=30.0,
        sand_pct=25.0,
        silt_pct=45.0,
        soc_g_kg=20.5,
        texture_class="Franco arcilloso",
        drainage_class="Moderado / Equilibrado",
        ph_class="Neutro (óptimo agrícola)",
        source="test",
    )

    veg = analyze_vegetation_health(climate, maiz, years_same_crop=3)
    assert veg.soil_exhaustion_risk == "Alto"
    assert "3 años seguidos" in veg.vegetation_alert

    scenarios = generate_rotation_scenarios(
        maiz, catalog, climate, terrain, soil, years_same_crop=3
    )
    assert len(scenarios) == 3
    crop_ids = {s.crop_id for s in scenarios}
    assert len(crop_ids) == 3
    assert "maiz" not in crop_ids
    for sc in scenarios:
        assert sc.sowing_window
        assert sc.economics.price_usd_ton > 0
        assert len(sc.rotation_sequence) == 3
