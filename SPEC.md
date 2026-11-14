# Especificación Técnica (`to-spec`): UI `shadcn/ui` + Impecable & Resiliencia Operativa

> Nota: Síntesis generada siguiendo el formato `to-spec`. Como este proyecto local no tiene un issue tracker conectado, se documenta aquí como especificación maestra de la iteración.

## Problem Statement

El frontend actual de AgroNASA funciona con estilos CSS escritos a mano y controles HTML nativos sin sistema de componentes estándar. La auditoría automatizada detectó antipatrones visuales (`side-tab` en alertas/tarjetas y tipografía genérica `Inter`), el bundle de producción supera el umbral recomendado en un único chunk (`734 kB`), y faltan estados de carga tipo *skeleton*, tooltips explicativos para métricas técnicas (`SMAP`, `ET₀`, `NDVI`) y un buscador geográfico en el mapa. En paralelo, el backend realiza llamadas externas repetidas sin caché local y el webhook de WhatsApp exige enviar cultivo y coordenadas en un único mensaje.

## Solution

Refactorizar la interfaz web hacia un sistema de componentes **`shadcn/ui` sobre Tailwind CSS**, diseñado bajo las directrices de **`impeccable`** (modo *Operate* para tablero agrícola diurno, cero antipatrones detectados por `impeccable detect`, tipografía de trabajo legible y jerarquía de alto contraste), separando las dependencias pesadas de mapas y gráficos en chunks independientes. Como siguiente paso técnico sobre el mismo contrato, incorporar caché geoespacial SQLite en el backend y flujo conversacional por pasos en WhatsApp.

## User Stories

1. As a farmer viewing the web dashboard outdoors, I want high-contrast, clean `shadcn/ui` cards and badges without cluttered side borders, so that I can scan climate, soil, and profit numbers effortlessly under daylight.
2. As a farmer unfamiliar with satellite acronyms, I want inline tooltips explaining `SMAP`, `ET₀`, `NDVI`, and `pH` in plain Spanish, so that I understand why each metric matters for my plot.
3. As a user waiting for NASA POWER, SRTM, and SoilGrids responses, I want structured skeleton loaders instead of a static spinner button alone, so that the dashboard feels responsive and predictable.
4. As a farmer inspecting monthly climate and channel previews, I want keyboard-accessible Radix-backed `Tabs` and `Select` controls, so that switching views works reliably on desktop and mobile browsers.
5. As a user selecting my farm on the map, I want clear visual feedback for point selection, polygon drawing, and the NASA MODIS NDVI layer toggle using consistent `shadcn/ui` button and badge primitives.
6. As a farmer sharing results with an agronomist or cooperative, I want a one-click "Compartir por WhatsApp" link and clean printable summary view, so that I can distribute recommendations directly from the web.
7. As a user on a slow rural connection, I want `recharts` and `leaflet` split into separate Vite chunks, so that initial page load is significantly faster.
8. As a backend consumer querying the same region repeatedly, I want geospatial satellite responses cached locally by grid cell (24h TTL), so that repeat queries resolve in milliseconds without external timeouts.
9. As a farmer querying via WhatsApp, I want to send my location pin first and pick my current crop from a numbered menu, so that I don't have to memorize command syntax.

## Implementation Decisions

- **Design System & `shadcn/ui` Architecture**:
  - Introduce Tailwind CSS with semantic HSL CSS tokens tuned for an agricultural *Operate* workspace (crisp off-white field paper surface, deep forest primary `#1B4332` / HSL equivalent, muted slate-sage secondary surfaces, warm ochre/emerald semantic states, zero `border-left` side-tabs).
  - Standardize UI primitives (`Button`, `Card`, `Badge`, `Tabs`, `Select`, `Alert`, `Tooltip`, `Skeleton`) following `shadcn/ui` conventions and Radix UI accessibility.
  - Replace `Inter` with a clean, non-overused workhorse UI sans + tabular numeric styling (`Work Sans` / system sans fallback + tabular numerals for coordinates, scores, and financial margins).
- **Dashboard & Map UX**:
  - Replace raw inline `<select>` and custom CSS tab buttons with `shadcn/ui` `Select` and `Tabs`.
  - Add a `DashboardSkeleton` component rendered while `recommendRotation` is in flight.
  - Add `TooltipProvider` explanations on technical KPIs (`ET₀`, `SMAP`, `NDVI`, `SoilGrids pH`).
  - Add a `wa.me` share action alongside the multi-channel preview so farmers can immediately forward their 3-scenario report via WhatsApp.
  - Configure Vite `manualChunks` separating `recharts`, `leaflet`, and `react` vendor bundles.
- **Backend Seams (Phase B/C readiness)**:
  - Preserve the existing `RecommendationOrchestrator` and REST contract (`/api/recommend-rotation`, `/api/channels/whatsapp/webhook`, `/api/channels/mobile/recommend`) without breaking schema compatibility.

## Testing Decisions

- **Frontend Verification**:
  - Production build (`npm run build`) must succeed cleanly without TypeScript/bundler errors and verify split chunks.
  - Run `impeccable detect --json` across all modified frontend source and CSS files, achieving **0 antipattern findings** (eliminating all `side-tab` and `overused-font` warnings).
  - Run live visual/HTTP smoke check against the running dev server (`localhost:5173`) and backend (`localhost:8000`).
- **Backend Verification**:
  - Keep all existing unit & API contract tests green (`pytest -v` covering NASA POWER, SRTM polygon/slope, SoilGrids/SSURGO, Market Economics, Rotation Engine, and Web/WhatsApp/Mobile endpoints).

## Out of Scope

- Live WhatsApp Business Meta Cloud API production webhook secrets and hosting deployment.
- Native iOS/Android Expo project scaffolding (deferred to the Mobile App phase).
- User authentication / multi-tenant PostgreSQL database setup.
