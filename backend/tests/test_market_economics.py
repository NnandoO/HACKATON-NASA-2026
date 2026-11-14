from app.services.market_economics import MarketEconomicsService
from app.services.crop_catalog import CropCatalog


def test_market_economics_evaluates_margin_and_nitrogen_savings():
    catalog = CropCatalog()
    econ = MarketEconomicsService()
    alfalfa = catalog.resolve("alfalfa")
    maiz = catalog.resolve("maiz")
    assert alfalfa is not None and maiz is not None

    alf_out = econ.evaluate_crop_economics(alfalfa, suitability_score=85.0)
    maiz_out = econ.evaluate_crop_economics(maiz, suitability_score=85.0)

    assert alf_out.fertilizer_savings_usd_ha > 150.0
    assert maiz_out.fertilizer_savings_usd_ha == 0.0
    assert alf_out.yoy_trend_pct == 8.0
    assert "USD" in alf_out.economic_summary
