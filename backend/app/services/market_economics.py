import json
from pathlib import Path
from typing import Dict, Optional

from app.config import settings
from app.schemas import CropRule, EconomicOutlook


class MarketEconomicsService:
    """Evaluates expected gross margin, market price trends, and N-fixation fertilizer savings."""

    def __init__(self, prices_path: Optional[str] = None) -> None:
        path = Path(prices_path or settings.market_prices_path)
        with path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        self.meta: Dict = raw.get("metadata", {})
        self.prices: Dict[str, Dict] = raw.get("prices", {})
        self.n_cost_per_kg = float(self.meta.get("nitrogen_fertilizer_cost_usd_per_kg", 1.25))

    def evaluate_crop_economics(
        self,
        crop: CropRule,
        suitability_score: float,
    ) -> EconomicOutlook:
        entry = self.prices.get(crop.id)
        if not entry:
            return EconomicOutlook(
                price_usd_ton=220.0,
                yoy_trend_pct=0.0,
                estimated_revenue_usd_ha=750.0,
                estimated_margin_usd_ha=180.0,
                fertilizer_savings_usd_ha=0.0,
                market_demand="Estable",
                economic_summary="Sin datos de referencia específicos; margen estimado conservador.",
                source="usda_ams_nass_reference",
            )

        price = float(entry["price_usd_ton"])
        base_yield = float(entry["avg_yield_ton_ha"])
        cost = float(entry["cost_usd_ha"])
        trend = float(entry["yoy_trend_pct"])
        demand = str(entry["market_demand"])

        # Adjust expected yield realistically by agronomic suitability score (0.65x to 1.05x)
        yield_factor = 0.55 + (suitability_score / 100.0) * 0.50
        adj_yield = base_yield * yield_factor
        revenue = round(adj_yield * price, 1)

        n_savings = 0.0
        if crop.nitrogen_balance_kg_ha > 0:
            n_savings = round(crop.nitrogen_balance_kg_ha * self.n_cost_per_kg, 1)

        margin = round(revenue - cost + n_savings, 1)
        trend_str = f"{trend:+.1f}%"
        savings_note = (
            f" + ahorro de USD {n_savings:.0f}/ha en urea por fijación de N."
            if n_savings > 0
            else "."
        )
        summary = (
            f"Precio ref. USD {price:.0f}/t ({trend_str} interanual, demanda {demand}); "
            f"margen neto est. USD {margin:.0f}/ha{savings_note}"
        )

        return EconomicOutlook(
            price_usd_ton=price,
            yoy_trend_pct=trend,
            estimated_revenue_usd_ha=revenue,
            estimated_margin_usd_ha=margin,
            fertilizer_savings_usd_ha=n_savings,
            market_demand=demand,
            economic_summary=summary,
            source="usda_ams_nass_reference",
        )
