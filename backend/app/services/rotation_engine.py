from typing import Dict, List, Optional, Tuple

from app.schemas import (
    ClimateAnalysis,
    CropRule,
    RotationScenario,
    SequenceStep,
    SoilProfile,
    TerrainAnalysis,
)
from app.services.crop_catalog import CropCatalog
from app.services.market_economics import MarketEconomicsService

FULL_MONTH_NAMES_ES = {
    1: "Enero",
    2: "Febrero",
    3: "Marzo",
    4: "Abril",
    5: "Mayo",
    6: "Junio",
    7: "Julio",
    8: "Agosto",
    9: "Septiembre",
    10: "Octubre",
    11: "Noviembre",
    12: "Diciembre",
}


def _range_fit_score(value: float, low: float, optimal: float, high: float, max_pts: float) -> Tuple[float, str]:
    """Score how well a metric fits [low, optimal, high] range."""
    if low <= value <= high:
        half_span = max(abs(optimal - low), abs(high - optimal), 1.0)
        closeness = max(0.0, 1.0 - abs(value - optimal) / (half_span * 1.35))
        score = max_pts * (0.6 + 0.4 * closeness)
        return score, "óptimo" if closeness >= 0.65 else "compatible"
    if value < low:
        deficit = (low - value) / max(low, 1.0)
        return max(0.0, max_pts * (0.45 - deficit)), "por debajo del mínimo"
    excess = (value - high) / max(high, 1.0)
    return max(0.0, max_pts * (0.45 - excess)), "por encima del máximo"


def _compute_sowing_window(candidate: CropRule, climate: ClimateAnalysis) -> str:
    """Select the best 2-month planting window using monthly NASA POWER climatology and SMAP wetness."""
    clim = climate.monthly_climatology
    if not clim:
        return "Inicio de temporada de lluvias"

    scored_months: List[Tuple[float, int]] = []
    for m in clim:
        score = 0.0
        if m.avg_rain_mm >= candidate.min_sowing_rain_mm:
            score += 2.0
        else:
            score -= (candidate.min_sowing_rain_mm - m.avg_rain_mm) * 0.05

        if m.avg_soil_wetness_top >= 0.45:
            score += 1.0

        if candidate.min_temp_c <= m.avg_temp_c <= candidate.max_temp_c:
            score += 2.0 - abs(m.avg_temp_c - candidate.optimal_temp_c) * 0.08
        else:
            score -= 2.0

        if candidate.frost_sensitive and m.avg_temp_min_c <= 3.0:
            score -= 4.0

        scored_months.append((score, m.month))

    score_by_m = {m: s for s, m in scored_months}
    best_pair_score = -999.0
    best_start = 1
    for m in range(1, 13):
        nxt = (m % 12) + 1
        pair_score = score_by_m.get(m, 0.0) + score_by_m.get(nxt, 0.0)
        if pair_score > best_pair_score:
            best_pair_score = pair_score
            best_start = m

    next_m = (best_start % 12) + 1
    return f"{FULL_MONTH_NAMES_ES[best_start]} – {FULL_MONTH_NAMES_ES[next_m]}"


def _build_multi_campaign_sequence(
    first_crop: CropRule,
    current_crop: CropRule,
    all_crops: List[CropRule],
    evaluations_by_id: Dict[str, Dict],
) -> List[SequenceStep]:
    """Construct a 3-campaign agronomic sequence starting with first_crop."""
    seq: List[SequenceStep] = [
        SequenceStep(
            campaign=1,
            crop_id=first_crop.id,
            crop_name=first_crop.name,
            role="Fijación de nitrógeno / recuperación inicial"
            if "fixer" in first_crop.nitrogen_effect
            else "Cultivo principal adaptado al lote",
        )
    ]

    candidates_c2 = [c for c in all_crops if c.id != first_crop.id]
    def _c2_score(c: CropRule) -> float:
        base = evaluations_by_id.get(c.id, {}).get("suitability_score", 50.0)
        bonus = 18.0 if c.crop_family != first_crop.crop_family else -8.0
        if "fixer" in first_crop.nitrogen_effect and "demand" in c.nitrogen_effect:
            bonus += 16.0
        elif "demand" in first_crop.nitrogen_effect and "fixer" in c.nitrogen_effect:
            bonus += 16.0
        return base + bonus

    c2 = max(candidates_c2, key=_c2_score)
    seq.append(
        SequenceStep(
            campaign=2,
            crop_id=c2.id,
            crop_name=c2.name,
            role="Aprovecha nitrógeno residual"
            if "fixer" in first_crop.nitrogen_effect and "demand" in c2.nitrogen_effect
            else "Corte biológico de plagas y reposición",
        )
    )

    candidates_c3 = [c for c in all_crops if c.id not in {first_crop.id, c2.id}]
    def _c3_score(c: CropRule) -> float:
        base = evaluations_by_id.get(c.id, {}).get("suitability_score", 50.0)
        bonus = 15.0 if c.crop_family != c2.crop_family else -6.0
        if "raices_profundas" in c.benefit_tags or "fija_nitrogeno" in c.benefit_tags:
            bonus += 10.0
        if c.id == current_crop.id:
            bonus -= 5.0
        return base + bonus

    c3 = max(candidates_c3, key=_c3_score)
    seq.append(
        SequenceStep(
            campaign=3,
            crop_id=c3.id,
            crop_name=c3.name,
            role="Estabilidad estructural y cierre de ciclo",
        )
    )
    return seq


def _evaluate_candidate(
    candidate: CropRule,
    current_crop: CropRule,
    climate: ClimateAnalysis,
    terrain: TerrainAnalysis,
    soil: SoilProfile,
    economics_svc: MarketEconomicsService,
    years_same_crop: int = 1,
) -> Dict:
    anomalies = climate.anomalies
    rain = anomalies.recent_annual_rain_mm
    temp = anomalies.recent_avg_temp_c
    slope = terrain.slope_pct

    # 1. Climate & Water balance fit (up to 36 pts)
    rain_score, rain_status = _range_fit_score(
        rain, candidate.min_rain_mm, candidate.optimal_rain_mm, candidate.max_rain_mm, 20.0
    )
    temp_score, temp_status = _range_fit_score(
        temp, candidate.min_temp_c, candidate.optimal_temp_c, candidate.max_temp_c, 16.0
    )

    # 2. Anomaly, SMAP soil wetness, frost & humidity adaptation (up to 16 pts)
    anomaly_pts = 5.0
    anomaly_reasons: List[str] = []
    if anomalies.drier_recent_trend or anomalies.water_balance_mm < -150.0:
        if candidate.drought_tolerance == "muy_alta":
            anomaly_pts += 9.0
            anomaly_reasons.append(f"alta tolerancia a sequía ante {anomalies.seasonal_focus_label.lower()} más seco")
        elif candidate.drought_tolerance == "alta":
            anomaly_pts += 6.0
            anomaly_reasons.append("buena resistencia hídrica ante menor humedad superficial")
        else:
            anomaly_pts -= 6.0
            anomaly_reasons.append("requiere vigilar humedad ante balance hídrico ajustado")

    if anomalies.hotter_recent_trend:
        if candidate.max_temp_c >= 33.0:
            anomaly_pts += 3.0
            anomaly_reasons.append("soporta temperaturas máximas elevadas")
        elif candidate.max_temp_c <= 28.0:
            anomaly_pts -= 4.0

    if anomalies.frost_risk_present:
        if not candidate.frost_sensitive:
            anomaly_pts += 5.0
            frost_fit = f"Tolerante a bajas temperaturas (mín. {anomalies.min_temp_coldest_month_c:.1f} °C)."
        else:
            anomaly_pts -= 6.0
            frost_fit = (
                f"Sensible a heladas (mín. {anomalies.min_temp_coldest_month_c:.1f} °C en {', '.join(anomalies.frost_risk_months) or 'invierno'}); sembrar fuera de meses fríos."
            )
    else:
        frost_fit = f"Sin riesgo limitante de heladas (mín. media {anomalies.min_temp_coldest_month_c:.1f} °C)."

    # Drainage vs waterlogging check
    if "Lento" in soil.drainage_class and candidate.waterlogging_tolerance == "baja":
        anomaly_pts -= 4.0

    # 3. Slope & erosion fit (up to 18 pts)
    if slope <= candidate.max_slope_pct:
        margin = candidate.max_slope_pct - slope
        slope_pts = 12.0 + min(6.0, margin * 0.6)
        if slope >= 5.0 and (
            "control_erosion" in candidate.benefit_tags
            or "raices_profundas" in candidate.benefit_tags
        ):
            slope_pts += 4.0
        if anomalies.extreme_rain_days_gt40mm >= 3 and (
            "control_erosion" in candidate.benefit_tags
            or "raices_profundas" in candidate.benefit_tags
        ):
            slope_pts += 3.0
            anomaly_reasons.append("protege el suelo frente a lluvias intensas diarias")
        slope_fit = (
            f"Apto para pendiente del lote ({slope:.1f}% ≤ máx. {candidate.max_slope_pct:.0f}%)."
        )
    else:
        excess_slope = slope - candidate.max_slope_pct
        slope_pts = max(-25.0, 4.0 - excess_slope * 4.0)
        slope_fit = (
            f"Precaución: pendiente ({slope:.1f}%) supera el límite sugerido ({candidate.max_slope_pct:.0f}%); usar curvas de nivel."
        )

    # 4. SoilGrids / SSURGO pH & Texture fit (up to 14 pts)
    ph_score, ph_status = _range_fit_score(
        soil.ph_h2o, candidate.min_ph, candidate.optimal_ph, candidate.max_ph, 14.0
    )
    if soil.ph_h2o < candidate.min_ph:
        soil_fit = (
            f"pH ({soil.ph_h2o:.1f}, {soil.texture_class}, drenaje {soil.drainage_class.lower()}) algo ácido para {candidate.name} (ideal {candidate.min_ph:.1f}-{candidate.max_ph:.1f})."
        )
    elif soil.ph_h2o > candidate.max_ph:
        soil_fit = (
            f"pH alcalino ({soil.ph_h2o:.1f}) sobre ideal ({candidate.max_ph:.1f}); {soil.texture_class}."
        )
    else:
        soil_fit = (
            f"Suelo {soil.texture_class} con pH {soil.ph_h2o:.1f} ({ph_status}) y drenaje {soil.drainage_class.lower()}."
        )

    # 5. Agronomic rotation synergy & monoculture break (up to 22 pts)
    agronomic_pts = 0.0
    synergy_reasons: List[str] = []

    if candidate.crop_family != current_crop.crop_family:
        monoculture_bonus = min(6.0, max(0, years_same_crop - 1) * 2.5)
        agronomic_pts += 10.0 + monoculture_bonus
        if years_same_crop >= 2:
            synergy_reasons.append(
                f"rompe {years_same_crop} años continuos de {current_crop.name} cambiando de familia botánica"
            )
        else:
            synergy_reasons.append(
                f"corta el ciclo de plagas y malezas de {current_crop.name} al cambiar de familia botánica"
            )
    else:
        agronomic_pts -= 8.0
        synergy_reasons.append(
            f"comparte familia botánica con {current_crop.name}, conviene reforzar manejo sanitario"
        )

    if current_crop.nitrogen_effect in ("high_demand", "medium_demand"):
        if candidate.nitrogen_effect == "high_fixer":
            agronomic_pts += 12.0
            synergy_reasons.append(
                f"repone intensamente el nitrógeno extraído por {current_crop.name} (+{candidate.nitrogen_balance_kg_ha:.0f} kg N/ha)"
            )
        elif candidate.nitrogen_effect == "medium_fixer":
            agronomic_pts += 9.0
            synergy_reasons.append(
                f"recupera nitrógeno consumido por {current_crop.name} (+{candidate.nitrogen_balance_kg_ha:.0f} kg N/ha)"
            )
    elif current_crop.nitrogen_effect in ("high_fixer", "medium_fixer"):
        if candidate.nitrogen_effect in ("high_demand", "medium_demand"):
            agronomic_pts += 9.0
            synergy_reasons.append(
                f"aprovecha el nitrógeno fijado previamente por {current_crop.name}"
            )

    if candidate.root_depth != current_crop.root_depth and candidate.root_depth in (
        "profunda",
        "muy_profunda",
    ):
        agronomic_pts += 4.0
        synergy_reasons.append("explora horizontes más profundos del suelo")

    raw_score = rain_score + temp_score + anomaly_pts + slope_pts + ph_score + agronomic_pts
    suitability_score = round(max(15.0, min(98.0, raw_score)), 1)

    if suitability_score >= 74.0:
        risk_level = "Bajo"
    elif suitability_score >= 54.0:
        risk_level = "Moderado"
    else:
        risk_level = "Alto"

    economics = economics_svc.evaluate_crop_economics(candidate, suitability_score)

    climate_fit = (
        f"Lluvia {rain:.0f} mm/año ({rain_status}) · ET₀ {anomalies.annual_et0_mm:.0f} mm · "
        f"Humedad suelo SMAP {anomalies.avg_soil_wetness_top * 100:.0f}% · Temp. {temp:.1f} °C ({temp_status})."
    )

    why_parts = []
    if synergy_reasons:
        first_reason = synergy_reasons[0]
        why_parts.append(first_reason[0].upper() + first_reason[1:])
        if len(synergy_reasons) > 1:
            why_parts.append(synergy_reasons[1])
    if anomaly_reasons:
        why_parts.append(anomaly_reasons[0])
    why_parts.append(
        f"margen est. USD {economics.estimated_margin_usd_ha:.0f}/ha ({economics.yoy_trend_pct:+.1f}% tendencia)"
    )

    why_suggested = "; ".join(why_parts) + "."
    sowing_window = _compute_sowing_window(candidate, climate)

    score_breakdown = {
        "Clima y agua": round(max(10.0, min(100.0, (rain_score + temp_score + max(0.0, anomaly_pts)) / 52.0 * 100.0)), 1),
        "Suelo y pH": round(max(10.0, min(100.0, ph_score / 14.0 * 100.0)), 1),
        "Topografía": round(max(10.0, min(100.0, max(0.0, slope_pts) / 22.0 * 100.0)), 1),
        "Regeneración": round(
            max(
                15.0,
                min(
                    100.0,
                    max(0.0, agronomic_pts + (6.0 if "fija_nitrogeno" in candidate.benefit_tags else 0.0)) / 30.0 * 100.0,
                ),
            ),
            1,
        ),
        "Rentabilidad": round(max(15.0, min(100.0, (economics.estimated_margin_usd_ha + 100.0) / 11.0)), 1),
    }

    return {
        "crop": candidate,
        "suitability_score": suitability_score,
        "score_breakdown": score_breakdown,
        "soil_score": suitability_score + (10.0 if "fija_nitrogeno" in candidate.benefit_tags else 0.0),
        "resilience_score": suitability_score
        + (10.0 if candidate.drought_tolerance in ("muy_alta", "alta") else 0.0)
        + (6.0 if slope <= candidate.max_slope_pct else -10.0),
        "market_score": suitability_score + min(15.0, max(-5.0, economics.estimated_margin_usd_ha / 65.0)) + max(0.0, economics.yoy_trend_pct * 0.5),
        "risk_level": risk_level,
        "sowing_window": sowing_window,
        "why_suggested": why_suggested,
        "climate_fit": climate_fit,
        "slope_fit": slope_fit,
        "soil_fit": soil_fit,
        "frost_fit": frost_fit,
        "economics": economics,
    }


def generate_rotation_scenarios(
    current_crop: CropRule,
    catalog: CropCatalog,
    climate: ClimateAnalysis,
    terrain: TerrainAnalysis,
    soil: SoilProfile,
    economics_svc: Optional[MarketEconomicsService] = None,
    years_same_crop: int = 1,
) -> List[RotationScenario]:
    """Generate 3 complementary crop rotation scenarios balancing soil, climate resilience & market profitability."""
    econ = economics_svc or MarketEconomicsService()
    all_crops = catalog.list_crops()
    candidates = [c for c in all_crops if c.id != current_crop.id]
    evaluations = [
        _evaluate_candidate(c, current_crop, climate, terrain, soil, econ, years_same_crop)
        for c in candidates
    ]
    evaluations_by_id = {ev["crop"].id: ev for ev in evaluations}

    picked_ids = set()
    scenarios: List[RotationScenario] = []

    strategy_specs = [
        (
            1,
            "Escenario 1: Regeneración de Suelo y Equilibrio Nutricional",
            "soil_score",
        ),
        (
            2,
            "Escenario 2: Resiliencia Climática y Eficiencia Hídrica",
            "resilience_score",
        ),
        (
            3,
            "Escenario 3: Rentabilidad de Mercado y Diversificación",
            "market_score",
        ),
    ]

    for rank, strategy_name, sort_key in strategy_specs:
        remaining = [ev for ev in evaluations if ev["crop"].id not in picked_ids]
        remaining.sort(key=lambda item: (item[sort_key], item["suitability_score"]), reverse=True)
        chosen = remaining[0]
        crop: CropRule = chosen["crop"]
        picked_ids.add(crop.id)

        sequence = _build_multi_campaign_sequence(
            first_crop=crop,
            current_crop=current_crop,
            all_crops=all_crops,
            evaluations_by_id=evaluations_by_id,
        )

        scenarios.append(
            RotationScenario(
                scenario_rank=rank,
                strategy_name=strategy_name,
                crop_id=crop.id,
                crop_name=crop.name,
                scientific_name=crop.scientific_name,
                category=crop.category,
                suitability_score=chosen["suitability_score"],
                risk_level=chosen["risk_level"],
                cycle_days=crop.cycle_days,
                sowing_window=chosen["sowing_window"],
                why_suggested=chosen["why_suggested"],
                soil_benefits=crop.soil_benefit,
                climate_fit=chosen["climate_fit"],
                slope_fit=chosen["slope_fit"],
                soil_fit=chosen["soil_fit"],
                frost_fit=chosen["frost_fit"],
                benefit_tags=crop.benefit_tags,
                economics=chosen["economics"],
                score_breakdown=chosen["score_breakdown"],
                rotation_sequence=sequence,
            )
        )

    return scenarios
