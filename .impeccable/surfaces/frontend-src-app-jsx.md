---
version: 1
slug: "frontend-src-app-jsx"
primary_target: "frontend/src/App.jsx"
related_targets: []
---

# Surface Brief — AgroNASA Web Dashboard

- **Mode:** operate
- **Scope:** Farmer & agronomist crop-rotation decision workspace (`frontend/src/App.jsx` and components).
- **Task:** Select parcel (point or polygon), pick current crop and monoculture duration, inspect satellite climate/SMAP/SRTM/SoilGrids/NDVI diagnostics, compare 3 rotation scenarios with market economics, and preview/share across Web, WhatsApp, and Mobile channels.

## Direction contract

THESIS: An agronomic field-ledger workspace built on crisp `shadcn/ui` primitives where satellite telemetry, soil chemistry, and crop profitability sit in disciplined tabular alignment without decorative side-borders or generic SaaS bloat.

OWN-WORLD: Restrained daylight-legible Operate palette: warm field-paper ground (`#F8F9F6`), pure card surfaces (`#FFFFFF`) bounded by 1px hairline sage borders, deep forest green primary actions (`#1E4D36`), semantic emerald/amber/crimson badges reserved strictly for agronomic risk and market trends, and `Public Sans` with `tabular-nums` for coordinates, scores, and USD/ha margins.

STORY: The farmer locates their field visually on the map, understands how local climate, SMAP soil moisture, slope, pH, and NDVI vigor constrain their parcel, and picks among three clear rotation paths backed by sowing windows, 3-campaign sequences, and market margin estimates.

FIRST VIEWPORT: Compact header bar with channel availability badges; split 2-column workspace pairing the interactive Leaflet parcel map (with polygon drawing and NASA MODIS NDVI overlay toggle) on the left with the `shadcn/ui` Radix Select configuration card and primary submit action on the right, followed below by Skeleton loading states, tabbed Recharts diagnostics, 3 comparative scenario cards, and the multi-channel WhatsApp/Mobile previewer.

FORM: User-pinned `shadcn/ui` + Tailwind Operate workspace (grounded candidate 5 adapted to `shadcn/ui`, seed:94dde7e553aadf24).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
