from app.schemas import (
    MobileRecommendationResponse,
    MobileScenarioCard,
    RecommendationResponse,
)


def to_mobile_response(rec: RecommendationResponse) -> MobileRecommendationResponse:
    """Create a compact, low-bandwidth payload optimized for mobile apps."""
    anomalies = rec.climate_analysis.anomalies
    terrain = rec.terrain_analysis
    soil = rec.soil_profile
    veg = rec.vegetation_health
    cards = [
        MobileScenarioCard(
            rank=sc.scenario_rank,
            crop_id=sc.crop_id,
            crop_name=sc.crop_name,
            strategy=sc.strategy_name,
            score=sc.suitability_score,
            risk=sc.risk_level,
            sowing_window=sc.sowing_window,
            estimated_margin_usd_ha=sc.economics.estimated_margin_usd_ha,
            price_trend_pct=sc.economics.yoy_trend_pct,
            why=sc.why_suggested,
            soil_benefit=sc.soil_benefits,
            sequence_summary=" → ".join(s.crop_name for s in sc.rotation_sequence),
        )
        for sc in rec.scenarios
    ]
    return MobileRecommendationResponse(
        coords=rec.location,
        current_crop_name=rec.current_crop.name,
        summary_badges={
            "climate_zone": anomalies.climate_zone,
            "elevation_m": terrain.elevation_m,
            "slope_pct": terrain.slope_pct,
            "area_ha": terrain.area_ha,
            "erosion_risk": terrain.erosion_risk,
            "soil_ph": soil.ph_h2o,
            "soil_texture": soil.texture_class,
            "smap_wetness_pct": round(anomalies.avg_soil_wetness_top * 100),
            "estimated_ndvi": veg.estimated_ndvi,
            "recent_temp_c": anomalies.recent_avg_temp_c,
            "temp_anomaly_c": anomalies.temp_anomaly_c,
            "recent_rain_mm": anomalies.recent_annual_rain_mm,
            "rain_anomaly_pct": anomalies.rain_anomaly_pct,
        },
        alerts=anomalies.climate_alerts + [veg.vegetation_alert],
        cards=cards,
    )
