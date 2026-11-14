from app.config import settings
from app.schemas import ClimateAnalysis, CropRule, VegetationHealth


def analyze_vegetation_health(
    climate: ClimateAnalysis,
    current_crop: CropRule,
    years_same_crop: int = 1,
) -> VegetationHealth:
    """Estimate vegetation vigor (NDVI index proxy + NASA GIBS MODIS layer) and monoculture exhaustion."""
    anomalies = climate.anomalies
    wet_root = anomalies.avg_soil_wetness_root
    rain_factor = min(1.0, anomalies.recent_annual_rain_mm / 900.0)

    # Calibrated NDVI vigor index (0.20 bare/stressed -> 0.85 vigorous canopy)
    raw_ndvi = 0.30 + 0.35 * wet_root + 0.20 * rain_factor
    if anomalies.drier_recent_trend and anomalies.hotter_recent_trend:
        raw_ndvi -= 0.08
    estimated_ndvi = round(max(0.22, min(0.86, raw_ndvi)), 2)

    if estimated_ndvi >= 0.62:
        ndvi_status = "Vigor alto (buena cobertura vegetal)"
    elif estimated_ndvi >= 0.45:
        ndvi_status = "Vigor moderado (estrés estacional leve)"
    else:
        ndvi_status = "Vigor bajo (estrés hídrico / cobertura escasa)"

    if years_same_crop >= 3:
        exhaustion = "Alto"
        alert = (
            f"Monocultivo detectado: {years_same_crop} años seguidos con {current_crop.name}. "
            "Riesgo elevado de agotamiento nutricional y acumulación de patógenos; rotación urgente recomendada."
        )
    elif years_same_crop == 2:
        exhaustion = "Moderado"
        alert = (
            f"Llevas 2 campañas consecutivas de {current_crop.name}. "
            "Conviene cambiar de familia botánica en el próximo ciclo para evitar caída de rendimiento."
        )
    else:
        exhaustion = "Bajo"
        alert = (
            f"Rotación preventiva tras {current_crop.name}: momento óptimo para alternar familia botánica y mantener vigor NDVI."
        )

    return VegetationHealth(
        estimated_ndvi=estimated_ndvi,
        ndvi_status=ndvi_status,
        ndvi_layer_url=settings.nasa_gibs_ndvi_wmts,
        monoculture_years=years_same_crop,
        soil_exhaustion_risk=exhaustion,
        vegetation_alert=alert,
        source="nasa_gibs_modis_ndvi+power_moisture_model",
    )
