from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChannelType(str, Enum):
    WEB = "web"
    WHATSAPP = "whatsapp"
    MOBILE = "mobile"


class LatLonPoint(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)


class CropRule(BaseModel):
    id: str
    name: str
    scientific_name: str
    crop_family: str
    category: str
    min_rain_mm: float
    max_rain_mm: float
    optimal_rain_mm: float
    min_temp_c: float
    max_temp_c: float
    optimal_temp_c: float
    max_slope_pct: float
    min_ph: float = 5.5
    max_ph: float = 7.8
    optimal_ph: float = 6.5
    frost_sensitive: bool = True
    min_sowing_rain_mm: float = 35.0
    kc_mid: float = 1.1
    waterlogging_tolerance: str = "media"
    nitrogen_balance_kg_ha: float = 0.0
    soil_benefit: str
    benefit_tags: List[str]
    nitrogen_effect: str
    root_depth: str
    drought_tolerance: str
    cycle_days: int


class RecommendationRequest(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitud de la parcela")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitud de la parcela")
    current_crop: str = Field(..., min_length=1, description="Cultivo actual o recién cosechado")
    years_same_crop: int = Field(
        default=1,
        ge=1,
        le=20,
        description="Años consecutivos sembrando el mismo cultivo (detección de monocultivo)",
    )
    channel: ChannelType = Field(default=ChannelType.WEB, description="Canal solicitante (web, whatsapp, mobile)")
    polygon: Optional[List[LatLonPoint]] = Field(
        default=None,
        description="Vértices opcionales del polígono del lote para calcular área y pendiente zonal",
    )


class MonthlyClimatePoint(BaseModel):
    period: str
    year: int
    month: int
    temp_c: float
    temp_max_c: Optional[float] = None
    temp_min_c: Optional[float] = None
    rh2m_pct: Optional[float] = None
    soil_wetness_top: Optional[float] = None
    soil_wetness_root: Optional[float] = None
    solar_mj_m2_day: Optional[float] = None
    et0_mm: Optional[float] = None
    rain_mm: float


class MonthlyClimatologyPoint(BaseModel):
    month: int
    month_name: str
    avg_temp_c: float
    avg_temp_min_c: float
    avg_rain_mm: float
    avg_rh2m_pct: float
    avg_soil_wetness_top: float
    avg_et0_mm: float


class AnnualClimatePoint(BaseModel):
    year: int
    avg_temp_c: float
    summer_avg_temp_c: float
    total_rain_mm: float
    summer_rain_mm: float
    avg_soil_wetness_top: float
    total_et0_mm: float


class ClimateAnomalies(BaseModel):
    climate_zone: str
    seasonal_focus_label: str
    baseline_period: str
    recent_period: str
    baseline_avg_temp_c: float
    recent_avg_temp_c: float
    temp_anomaly_c: float
    summer_temp_anomaly_c: float
    baseline_annual_rain_mm: float
    recent_annual_rain_mm: float
    rain_anomaly_pct: float
    summer_rain_anomaly_pct: float
    min_temp_coldest_month_c: float
    avg_rh2m_pct: float
    avg_soil_wetness_top: float
    avg_soil_wetness_root: float
    dry_soil_months: List[str]
    annual_et0_mm: float
    water_balance_mm: float
    extreme_rain_days_gt40mm: int = 0
    heavy_rain_days_gt25mm: int = 0
    max_daily_rain_mm: float = 0.0
    frost_risk_months: List[str]
    drier_recent_trend: bool
    hotter_recent_trend: bool
    frost_risk_present: bool
    high_humidity_risk: bool
    climate_alerts: List[str]


class ClimateAnalysis(BaseModel):
    source: str
    hemisphere: str
    anomalies: ClimateAnomalies
    annual_series: List[AnnualClimatePoint]
    recent_monthly_series: List[MonthlyClimatePoint]
    monthly_climatology: List[MonthlyClimatologyPoint]


class TerrainAnalysis(BaseModel):
    elevation_m: float
    min_elevation_m: float
    max_elevation_m: float
    slope_pct: float
    max_slope_pct: float
    slope_deg: float
    terrain_class: str
    source: str
    erosion_risk: str
    area_ha: Optional[float] = None
    polygon_vertices: int = 0
    is_ocean: bool = False


class SoilProfile(BaseModel):
    ph_h2o: float
    clay_pct: float
    sand_pct: float
    silt_pct: float
    soc_g_kg: float
    texture_class: str
    drainage_class: str
    ph_class: str
    usda_ssurgo_mapunit: Optional[str] = None
    source: str


class NdviHistoryPoint(BaseModel):
    date: str
    ndvi: float
    source: str


class CdlCropYear(BaseModel):
    year: int
    code: int
    category: str
    mapped_crop_id: Optional[str] = None


class VegetationHealth(BaseModel):
    estimated_ndvi: float
    ndvi_status: str
    ndvi_layer_url: str
    monoculture_years: int
    soil_exhaustion_risk: str
    vegetation_alert: str
    source: str
    ndvi_series: List[NdviHistoryPoint] = Field(default_factory=list)
    cdl_history: List[CdlCropYear] = Field(default_factory=list)
    auto_detected_monoculture_years: Optional[int] = None


class EconomicOutlook(BaseModel):
    price_usd_ton: float
    yoy_trend_pct: float
    estimated_revenue_usd_ha: float
    estimated_margin_usd_ha: float
    fertilizer_savings_usd_ha: float
    market_demand: str
    economic_summary: str
    source: str


class SequenceStep(BaseModel):
    campaign: int
    crop_id: str
    crop_name: str
    role: str


class RotationScenario(BaseModel):
    scenario_rank: int
    strategy_name: str
    crop_id: str
    crop_name: str
    scientific_name: str
    category: str
    suitability_score: float
    risk_level: str
    cycle_days: int
    sowing_window: str
    why_suggested: str
    soil_benefits: str
    climate_fit: str
    slope_fit: str
    soil_fit: str
    frost_fit: str
    benefit_tags: List[str]
    economics: EconomicOutlook
    score_breakdown: Optional[Dict[str, float]] = None
    rotation_sequence: List[SequenceStep]


class RecommendationResponse(BaseModel):
    channel: ChannelType
    location: Dict[str, float]
    current_crop: CropRule
    climate_analysis: ClimateAnalysis
    terrain_analysis: TerrainAnalysis
    soil_profile: SoilProfile
    vegetation_health: VegetationHealth
    scenarios: List[RotationScenario]
    data_provenance: Optional[Dict[str, Any]] = None
    channel_payload: Optional[Dict[str, Any]] = None


class WhatsAppIncomingMessage(BaseModel):
    from_number: str = Field(default="whatsapp:+549000000000")
    body: str = Field(default="", description="Ej: 'rotacion maiz -31.48, -63.55'")
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)


class WhatsAppOutgoingMessage(BaseModel):
    to_number: str
    reply_text: str
    parsed_intent: Dict[str, Any]
    recommendation: Optional[RecommendationResponse] = None


class MobileScenarioCard(BaseModel):
    rank: int
    crop_id: str
    crop_name: str
    strategy: str
    score: float
    risk: str
    sowing_window: str
    estimated_margin_usd_ha: float
    price_trend_pct: float
    why: str
    soil_benefit: str
    sequence_summary: str


class MobileRecommendationResponse(BaseModel):
    channel: ChannelType = ChannelType.MOBILE
    coords: Dict[str, float]
    current_crop_name: str
    summary_badges: Dict[str, Any]
    alerts: List[str]
    cards: List[MobileScenarioCard]
