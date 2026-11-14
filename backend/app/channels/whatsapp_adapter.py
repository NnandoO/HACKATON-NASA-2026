import re
from typing import Any, Dict, Optional, Tuple

from app.schemas import RecommendationResponse, WhatsAppIncomingMessage, WhatsAppOutgoingMessage
from app.services.crop_catalog import CropCatalog
from app.services.geo_cache import geo_cache

COORD_PATTERN = re.compile(r"(-?\d{1,2}\.\d+|-?\d{1,2})\s*[,;\s]\s*(-?\d{1,3}\.\d+|-?\d{1,3})")
STRICT_DECIMAL_COORD_PATTERN = re.compile(r"(-?\d{1,2}\.\d+)\s*[,;\s]\s*(-?\d{1,3}\.\d+)")
YEARS_PATTERN = re.compile(r"(\d{1,2})\s*(?:años|año|anos|ano|campañas|campanas)")

SESSION_TTL_SECONDS = 1800


def _extract_years(body: str) -> int:
    match = YEARS_PATTERN.search((body or "").lower())
    if not match:
        return 1
    return max(1, min(20, int(match.group(1))))


def parse_whatsapp_message(
    msg: WhatsAppIncomingMessage,
    catalog: CropCatalog,
) -> Dict[str, Any]:
    """Extract coordinates, crop (name or menu index), and monoculture years from WhatsApp."""
    lat: Optional[float] = msg.latitude
    lon: Optional[float] = msg.longitude
    body = (msg.body or "").strip()

    cleaned_for_tokens = body.lower()
    if lat is None or lon is None:
        match = STRICT_DECIMAL_COORD_PATTERN.search(body) or (
            COORD_PATTERN.search(body) if ("," in body or ";" in body) else None
        )
        if match:
            cand_lat = float(match.group(1))
            cand_lon = float(match.group(2))
            if -90.0 <= cand_lat <= 90.0 and -180.0 <= cand_lon <= 180.0:
                lat, lon = cand_lat, cand_lon
                cleaned_for_tokens = (body[: match.start()] + " " + body[match.end() :]).lower()

    years_same_crop = _extract_years(body)
    cleaned_no_years = YEARS_PATTERN.sub(" ", cleaned_for_tokens)

    crops = catalog.list_crops()
    detected_crop = None

    for token in re.split(r"[\s,;:|]+", cleaned_no_years):
        if not token:
            continue
        if token.isdigit():
            idx = int(token)
            if 1 <= idx <= len(crops):
                detected_crop = crops[idx - 1]
                break
            continue
        if len(token) < 3 or token in {"rotacion", "rotación", "cultivo", "parcela", "hola", "ayuda", "reset", "reiniciar"}:
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
        "years_same_crop": years_same_crop,
        "reset_requested": any(w in body.lower() for w in ("reset", "reiniciar", "ayuda", "help")),
    }


def format_whatsapp_reply(rec: RecommendationResponse) -> str:
    """Format the 3 multi-pillar scenarios (Climate/SMAP, Soil, NDVI, FAO, Market) for WhatsApp."""
    anomalies = rec.climate_analysis.anomalies
    terrain = rec.terrain_analysis
    soil = rec.soil_profile
    veg = rec.vegetation_health

    area_text = f" | Área {terrain.area_ha:.2f} ha" if terrain.area_ha is not None else ""
    storm_text = (
        f" | Lluvia máx {anomalies.max_daily_rain_mm:.0f} mm/día"
        if anomalies.max_daily_rain_mm > 0
        else ""
    )
    lines = [
        f"*AgroNASA - Rotación recomendada tras {rec.current_crop.name}*",
        f"Parcela: {rec.location['lat']:.4f}, {rec.location['lon']:.4f}{area_text}",
        f"Terreno (SRTM): {terrain.elevation_m:.0f} m s.n.m. | Pendiente {terrain.slope_pct:.1f}% ({terrain.terrain_class})",
        f"Suelo: {soil.texture_class} | pH {soil.ph_h2o:.1f} | Drenaje {soil.drainage_class}",
        f"Clima ({anomalies.climate_zone}): {anomalies.recent_avg_temp_c:.1f} °C ({anomalies.temp_anomaly_c:+.1f} °C) | {anomalies.recent_annual_rain_mm:.0f} mm/año{storm_text} | Humedad SMAP {anomalies.avg_soil_wetness_top * 100:.0f}%",
        f"Vegetación NDVI: {veg.estimated_ndvi:.2f} ({veg.ndvi_status})",
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

    lines.append("Envía una nueva ubicación o cultivo para consultar otro lote.")
    return "\n".join(lines).strip()


def _format_crop_menu(catalog: CropCatalog, lat: float, lon: float) -> str:
    crops = catalog.list_crops()
    menu_lines = [f"{idx}) {crop.name}" for idx, crop in enumerate(crops, start=1)]
    return (
        f"*Ubicación recibida* ({lat:.4f}, {lon:.4f})\n"
        "¿Cuál es tu cultivo actual o recién cosechado? Respondé con el *número* o *nombre*:\n"
        + "\n".join(menu_lines)
        + "\n\n_Tip: podés sumar años seguidos, ej: `1 3 años`_"
    )


def build_whatsapp_help(catalog: CropCatalog) -> str:
    crops = ", ".join(f"{idx}) {c.name}" for idx, c in enumerate(catalog.list_crops(), start=1))
    return (
        "*Bienvenido a AgroNASA por WhatsApp*\n"
        "Podés consultar de 2 formas:\n"
        "1️⃣ *En 2 pasos*: enviá primero tu *ubicación GPS* (o `-31.48, -63.55`) y luego elegí el cultivo.\n"
        "2️⃣ *Todo junto*: `rotacion maiz -31.48, -63.55`\n\n"
        f"Cultivos: {crops}."
    )


def _clear_session(from_number: str) -> None:
    geo_cache.set_json("whatsapp_session", from_number, {}, ttl_seconds=60)


def handle_whatsapp_query(
    msg: WhatsAppIncomingMessage,
    orchestrator: Any,
) -> Tuple[WhatsAppOutgoingMessage, Optional[RecommendationResponse]]:
    parsed = parse_whatsapp_message(msg, orchestrator.catalog)
    session = geo_cache.get_json("whatsapp_session", msg.from_number) or {}

    if parsed["reset_requested"] and parsed["lat"] is None and parsed["crop_id"] is None:
        _clear_session(msg.from_number)
        return (
            WhatsAppOutgoingMessage(
                to_number=msg.from_number,
                reply_text=build_whatsapp_help(orchestrator.catalog),
                parsed_intent={**parsed, "step": "help"},
                recommendation=None,
            ),
            None,
        )

    lat = parsed["lat"] if parsed["lat"] is not None else session.get("lat")
    lon = parsed["lon"] if parsed["lon"] is not None else session.get("lon")
    crop_id = parsed["crop_id"] if parsed["crop_id"] is not None else session.get("crop_id")
    crop_name = parsed["crop_name"] if parsed["crop_name"] is not None else session.get("crop_name")
    years = parsed["years_same_crop"] if parsed["years_same_crop"] > 1 else session.get("years_same_crop", 1)

    # Step 1a: Location received, waiting for crop
    if lat is not None and lon is not None and crop_id is None:
        geo_cache.set_json(
            "whatsapp_session",
            msg.from_number,
            {"lat": lat, "lon": lon},
            ttl_seconds=SESSION_TTL_SECONDS,
        )
        return (
            WhatsAppOutgoingMessage(
                to_number=msg.from_number,
                reply_text=_format_crop_menu(orchestrator.catalog, lat, lon),
                parsed_intent={**parsed, "lat": lat, "lon": lon, "step": "awaiting_crop"},
                recommendation=None,
            ),
            None,
        )

    # Step 1b: Crop received, waiting for location
    if crop_id is not None and (lat is None or lon is None):
        geo_cache.set_json(
            "whatsapp_session",
            msg.from_number,
            {"crop_id": crop_id, "crop_name": crop_name, "years_same_crop": years},
            ttl_seconds=SESSION_TTL_SECONDS,
        )
        return (
            WhatsAppOutgoingMessage(
                to_number=msg.from_number,
                reply_text=(
                    f"Cultivo seleccionado: *{crop_name}* ({years} año/s).\n"
                    "Ahora enviá tu *ubicación GPS de WhatsApp* o escribí las coordenadas (ej: `-31.48, -63.55`)."
                ),
                parsed_intent={**parsed, "crop_id": crop_id, "step": "awaiting_location"},
                recommendation=None,
            ),
            None,
        )

    # Neither available
    if lat is None or lon is None or crop_id is None:
        return (
            WhatsAppOutgoingMessage(
                to_number=msg.from_number,
                reply_text=build_whatsapp_help(orchestrator.catalog),
                parsed_intent={**parsed, "step": "help"},
                recommendation=None,
            ),
            None,
        )

    from app.schemas import ChannelType

    _clear_session(msg.from_number)
    merged_intent = {
        "lat": lat,
        "lon": lon,
        "crop_id": crop_id,
        "crop_name": crop_name,
        "years_same_crop": years,
        "step": "completed",
    }

    try:
        rec = orchestrator.recommend(
            lat=lat,
            lon=lon,
            current_crop_query=crop_id,
            channel=ChannelType.WHATSAPP,
            years_same_crop=years,
        )
    except ValueError as exc:
        return (
            WhatsAppOutgoingMessage(
                to_number=msg.from_number,
                reply_text=f"No se pudo analizar esa ubicación:\n{exc}",
                parsed_intent=merged_intent,
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
            parsed_intent=merged_intent,
            recommendation=rec,
        ),
        rec,
    )
