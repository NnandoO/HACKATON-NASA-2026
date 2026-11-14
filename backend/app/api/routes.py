from typing import Optional
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, Form, HTTPException, Query
from fastapi.responses import Response

from app.channels.base import RecommendationOrchestrator
from app.channels.mobile_presenter import to_mobile_response
from app.channels.web_presenter import attach_channel_previews
from app.channels.whatsapp_adapter import handle_whatsapp_query
from app.services.geo_cache import geo_cache
from app.schemas import (
    ChannelType,
    CropRule,
    MobileRecommendationResponse,
    RecommendationRequest,
    RecommendationResponse,
    WhatsAppIncomingMessage,
    WhatsAppOutgoingMessage,
)

router = APIRouter(prefix="/api", tags=["AgroNASA"])
orchestrator = RecommendationOrchestrator()


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "channels": ["web", "whatsapp", "mobile"],
        "pillars": [
            "nasa_power_smap_water",
            "srtm_soilgrids_ssurgo",
            "nasa_gibs_ndvi_vegetation",
            "fao_gaez_usda_rules",
            "market_economics",
        ],
        "crops_loaded": len(orchestrator.catalog.list_crops()),
        "cache": geo_cache.stats(),
    }


@router.get("/crops", response_model=list[CropRule])
def list_crops():
    """Return FAO-based crop rules catalog shared across all 3 channels."""
    return orchestrator.catalog.list_crops()


def _execute_recommendation(req: RecommendationRequest) -> RecommendationResponse:
    try:
        rec = orchestrator.recommend(
            lat=req.lat,
            lon=req.lon,
            current_crop_query=req.current_crop,
            channel=req.channel,
            polygon=req.polygon,
            years_same_crop=req.years_same_crop,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return attach_channel_previews(rec)


@router.post("/recommend-rotation", response_model=RecommendationResponse)
def recommend_rotation_post(payload: RecommendationRequest):
    """Core REST endpoint returning 3 crop rotation scenarios across all 5 data pillars."""
    return _execute_recommendation(payload)


@router.get("/recommend-rotation", response_model=RecommendationResponse)
def recommend_rotation_get(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
    current_crop: str = Query(..., min_length=1),
    years_same_crop: int = Query(default=1, ge=1, le=20),
    channel: ChannelType = Query(default=ChannelType.WEB),
):
    """GET variant of /api/recommend-rotation for quick queries."""
    return _execute_recommendation(
        RecommendationRequest(
            lat=lat,
            lon=lon,
            current_crop=current_crop,
            years_same_crop=years_same_crop,
            channel=channel,
        )
    )


@router.post("/channels/whatsapp/webhook", response_model=WhatsAppOutgoingMessage)
def whatsapp_webhook(payload: WhatsAppIncomingMessage):
    """Channel adapter for WhatsApp (JSON / Meta Cloud API & Web simulator, 1-step or 2-step)."""
    outgoing, _ = handle_whatsapp_query(payload, orchestrator)
    return outgoing


@router.post("/channels/whatsapp/twilio")
def whatsapp_twilio_webhook(
    From: str = Form(default="whatsapp:+549000000000"),
    Body: str = Form(default=""),
    Latitude: Optional[float] = Form(default=None),
    Longitude: Optional[float] = Form(default=None),
):
    """Twilio WhatsApp webhook compatible endpoint (form-urlencoded -> TwiML XML)."""
    outgoing, _ = handle_whatsapp_query(
        WhatsAppIncomingMessage(
            from_number=From,
            body=Body,
            latitude=Latitude,
            longitude=Longitude,
        ),
        orchestrator,
    )
    twiml = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{xml_escape(outgoing.reply_text)}</Message></Response>'
    return Response(content=twiml, media_type="application/xml")


@router.post("/channels/mobile/recommend", response_model=MobileRecommendationResponse)
def mobile_recommend(payload: RecommendationRequest):
    """Channel adapter returning lightweight cards optimized for mobile apps."""
    try:
        rec = orchestrator.recommend(
            lat=payload.lat,
            lon=payload.lon,
            current_crop_query=payload.current_crop,
            channel=ChannelType.MOBILE,
            polygon=payload.polygon,
            years_same_crop=payload.years_same_crop,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return to_mobile_response(rec)
