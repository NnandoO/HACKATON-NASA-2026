from app.channels.mobile_presenter import to_mobile_response
from app.channels.whatsapp_adapter import format_whatsapp_reply
from app.schemas import RecommendationResponse


def attach_channel_previews(rec: RecommendationResponse) -> RecommendationResponse:
    """Attach ready-to-render WhatsApp and Mobile payloads for multi-channel inspection."""
    rec.channel_payload = {
        "whatsapp_message": format_whatsapp_reply(rec),
        "mobile_compact": to_mobile_response(rec).model_dump(),
    }
    return rec
