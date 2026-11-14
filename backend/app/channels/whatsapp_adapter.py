import re
from typing import Any, Dict, Optional, Tuple

from app.schemas import RecommendationResponse, WhatsAppIncomingMessage, WhatsAppOutgoingMessage
from app.services.crop_catalog import CropCatalog

COORD_PATTERN = re.compile(r"(-?\d{1,2}(?:\.\d+)?)\s*[,;\s]\s*(-?\d{1,3}(?:\.\d+)?)")


def parse_whatsapp_message(
    msg: WhatsAppIncomingMessage,
    catalog: CropCatalog,
) -> Dict[str, Any]:
    """Extract crop and coordinates from a WhatsApp text or location pin message."""
    lat: Optional[float] = msg.latitude
    lon: Optional[float] = msg.longitude

    body = (msg.body or "").strip()
    if lat is None or lon is None:
        match = COORD_PATTERN.search(body)
        if match:
            cand_lat = float(match.group(1))
            cand_lon = float(match.group(2))
            if -90.0 <= cand_lat <= 90.0 and -180.0 <= cand_lon <= 180.0:
                lat, lon = cand_lat, cand_lon

    detected_crop = None
    cleaned = COORD_PATTERN.sub(" ", body.lower())
    for token in re.split(r"[\s,;:|]+", cleaned):
        if len(token) < 3 or token in {"rotacion", "rotación", "cultivo", "parcela", "hola", "ayuda"}:
            continue
        crop = catalog.resolve(token)
        if crop is not None:
            detected_crop = crop
            break

    return {
        "lat": lat,
        "lon": lon,
        "crop_id": detected_crop.id if detected_crop else None,
        "crop_name": detected_crop.name if detected_crop else None,
    }


def format_whatsapp_reply(rec: RecommendationResponse) -> str:
    """Format the 3 multi-pillar scenarios (Climate/SMAP, Soil, NDVI, FAO, Market) for WhatsApp."""
    anomalies = rec.climate_analysis.anomalies
    terrain = rec.terrain_analysis
    soil = rec.soil_profile
    veg = rec.vegetation_health

    area_text = f" | Área {terrain.area_ha:.2f} ha" if terrain.area_ha is not None else ""
    lines = [
        f"*AgroNASA - Rotación recomendada tras {rec.current_crop.name}*",
        f"Parcela: {rec.location['lat']:.4f}, {rec.location['lon']:.4f}{area_text}",
        f"Terreno (SRTM): {terrain.elevation_m:.0f} m s.n.m. | Pendiente {terrain.slope_pct:.1f}% ({terrain.terrain_class})",
        f"Suelo: {soil.texture_class} | pH {soil.ph_h2o:.1f} | Drenaje {soil.drainage_class}",
        f"Clima ({anomalies.climate_zone}): {anomalies.recent_avg_temp_c:.1f} °C ({anomalies.temp_anomaly_c:+.1f} °C) | {anomalies.recent_annual_rain_mm:.0f} mm/año | Humedad SMAP {anomalies.avg_soil_wetness_top * 100:.0f}%",
        f"Vegetación NDVI est.: {veg.estimated_ndvi:.2f} ({veg.ndvi_status})",
        "",
        "*3 Escenarios sugeridos:*",
    ]

    for sc in rec.scenarios:
        seq_str = " → ".join(step.crop_name for step in sc.rotation_sequence)
        lines.extend(
            [
                f"*{sc.scenario_rank}) {sc.crop_name}* ({sc.suitability_score:.0f}/100 · Margen est. USD {sc.economics.estimated_margin_usd_ha:.0f}/ha)",
                f"• _Siembra ideal_: {sc.sowing_window}",
                f"• _Por qué_: {sc.why_suggested}",
                f"• _Beneficio al suelo_: {sc.soil_benefits}",
                f"• _Secuencia 3 campañas_: {seq_str}",
                "",
            ]
        )

    lines.append("Envía otro cultivo + ubicación para comparar más opciones.")
    return "\n".join(lines).strip()


def build_whatsapp_help(catalog: CropCatalog) -> str:
    crops = ", ".join(c.name for c in catalog.list_crops())
    return (
        "*Bienvenido a AgroNASA por WhatsApp*\n"
        "Comparte tu ubicación o escribe el cultivo actual y coordenadas:\n"
        "Ejemplo: `rotacion maiz -31.48, -63.55`\n\n"
        f"Cultivos disponibles: {crops}."
    )


def handle_whatsapp_query(
    msg: WhatsAppIncomingMessage,
    orchestrator: Any,
) -> Tuple[WhatsAppOutgoingMessage, Optional[RecommendationResponse]]:
    parsed = parse_whatsapp_message(msg, orchestrator.catalog)
    if parsed["lat"] is None or parsed["lon"] is None or parsed["crop_id"] is None:
        return (
            WhatsAppOutgoingMessage(
                to_number=msg.from_number,
                reply_text=build_whatsapp_help(orchestrator.catalog),
                parsed_intent=parsed,
                recommendation=None,
            ),
            None,
        )

    from app.schemas import ChannelType

    try:
        rec = orchestrator.recommend(
            lat=parsed["lat"],
            lon=parsed["lon"],
            current_crop_query=parsed["crop_id"],
            channel=ChannelType.WHATSAPP,
        )
    except ValueError as exc:
        return (
            WhatsAppOutgoingMessage(
                to_number=msg.from_number,
                reply_text=f"No se pudo analizar esa ubicación:\n{exc}",
                parsed_intent=parsed,
                recommendation=None,
            ),
            None,
        )
    reply = format_whatsapp_reply(rec)
    rec.channel_payload = {"whatsapp_text": reply}
    return (
        WhatsAppOutgoingMessage(
            to_number=msg.from_number,
            reply_text=reply,
            parsed_intent=parsed,
            recommendation=rec,
        ),
        rec,
    )
