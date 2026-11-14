# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary users are farmers and field agronomists (Spanish-speaking primary audience across Latin America, with US SSURGO support) deciding what crop to plant next on a specific parcel. Inferred operating context: field and office use under daylight glare on laptops, tablets, or smartphones, often with intermittent rural connectivity.

## Product Purpose

AgroNASA translates raw satellite Earth-observation datasets and agronomic rules into three clear, comparable crop rotation scenarios for a farmer's exact plot, answering why each crop fits, how it regenerates the soil, when to sow it, and what economic margin to expect.

## Positioning

Unlike generic farming blogs or raw meteorological portals, AgroNASA cross-references five live pillars on a single parcel (NASA POWER + SMAP-assimilated soil wetness and ET₀, NASA SRTM 90m slope/polygon relief, ISRIC SoilGrids + USDA SSURGO soil profile, NASA GIBS MODIS NDVI + monoculture exhaustion check, and FAO GAEZ / market economics) and delivers identical recommendations across Web, WhatsApp, and Mobile API channels.

## Operating Context

- Farmers select a parcel visually by clicking on a map or drawing a polygon to measure hectares and zonal slope, without typing latitude/longitude manually.
- Users specify their current/harvested crop and consecutive years planted (`1`, `2`, `3+` monoculture alert).
- Decisions rely on scanning climate anomalies, water balance, soil pH/texture, sowing windows, and comparing three strategic rotation cards side-by-side.
- The web UI also hosts live previews for the WhatsApp webhook and low-bandwidth Mobile App channel.

## Capabilities and Constraints

- Existing stack: Python FastAPI backend (`pandas`, `httpx`, `pydantic`) and React 18 + Vite frontend (`react-leaflet`, `recharts`, `lucide-react`), migrating UI layer to `shadcn/ui` + Tailwind CSS (explicitly requested by user).
- Multi-channel REST surface: `/api/crops`, `/api/recommend-rotation`, `/api/channels/whatsapp/webhook`, `/api/channels/mobile/recommend`.
- Eight base crops (`maiz`, `trigo`, `sorgo`, `alfalfa`, `soja`, `frijol`, `girasol`, `garbanzo`) with FAO GAEZ/USDA Ag Data Commons parameters.
- External API resilience constraint: NASA POWER, OpenTopoData SRTM, ISRIC SoilGrids, and USDA SSURGO must degrade gracefully to deterministic fallbacks when offline or rate-limited, clearly marking data provenance.
- Undecided / out of current scope: persistent user accounts, live Twilio/Meta production credentials, and real-time regional commodity exchange API keys.

## Evidence on Hand

- Live API integrations verified in codebase: NASA POWER monthly agroclimatology (`T2M`, `T2M_MAX`, `T2M_MIN`, `PRECTOTCORR`, `RH2M`, `GWETTOP`, `GWETROOT`, `ALLSKY_SFC_SW_DWN`), OpenTopoData SRTM 90m, ISRIC SoilGrids v2.0, USDA SSURGO Soil Data Access, and NASA GIBS `MODIS_Terra_NDVI_8Day` WMTS tiles.
- Simulated reference datasets in repository: `data/fao_crops_rules.json` (v3.0.0) and `data/market_prices_reference.json` (USDA AMS/NASS reference figures).

## Product Principles

1. **Field-ready clarity over scientific jargon:** Translate satellite indicators (`ET₀`, `SMAP`, `NDVI`, `pH`) into plain agronomic consequences and concrete sowing/soil actions.
2. **Agronomy and profitability together:** Never recommend a soil-improving crop without showing its expected margin, input savings, and market demand trend.
3. **Channel parity from one core:** Web, WhatsApp, and Mobile share one deterministic recommendation engine.
4. **Honest provenance and resilience:** Always distinguish live satellite/survey measurements from offline fallback estimates.

## Accessibility & Inclusion

Inferred requirement: WCAG AA contrast (≥ 4.5:1 body text) and full keyboard navigation across form controls, tabs, and tooltips for daylight readability and accessible web operation.
