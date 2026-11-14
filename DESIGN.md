---
name: AgroNASA Design System
description: High-clarity agronomic decision workbench combining warm field-paper surfaces, forest-pine primary actions, and tabular scientific telemetry across Web, WhatsApp, and Mobile previews.
colors:
  background: "#f7f9f5"
  foreground: "#16271d"
  card: "#ffffff"
  primary: "#1e4d36"
  primary-foreground: "#fafbf8"
  secondary: "#eaece7"
  secondary-foreground: "#1d3528"
  muted: "#edf0ea"
  muted-foreground: "#556c5d"
  border: "#d3dbd0"
  destructive: "#c52020"
  success: "#065f46"
  warning: "#92400e"
typography:
  sans: '"Public Sans", system-ui, -apple-system, sans-serif'
  base-size: 1rem
  heading-weight: 700
  body-weight: 400
rounded:
  sm: 6px
  md: 8px
  lg: 10px
  xl: 12px
  full: 9999px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 20px
  xl: 24px
  2xl: 32px
components:
  button-primary:
    background: "{colors.primary}"
    color: "{colors.primary-foreground}"
    radius: "{rounded.md}"
    padding: 8px 16px
    font-weight: 600
    transition: 150ms
  button-outline:
    background: "{colors.card}"
    color: "{colors.foreground}"
    border: 1px solid {colors.border}
    radius: "{rounded.md}"
    padding: 8px 16px
    font-weight: 500
  card:
    background: "{colors.card}"
    border: 1px solid {colors.border}
    radius: "{rounded.xl}"
    padding: 20px
    shadow: 0 2px 10px rgba(20, 40, 28, 0.04)
  badge-success:
    background: "#ecfdf5"
    color: "{colors.success}"
    border: 1px solid #a7f3d0
    radius: "{rounded.md}"
    padding: 2px 10px
    font-weight: 600
  input:
    background: "{colors.background}"
    color: "{colors.foreground}"
    border: 1px solid {colors.border}
    radius: "{rounded.md}"
    padding: 8px 12px
---

## Overview

AgroNASA pairs warm, daylight-legible field-paper surfaces (`#f7f9f5`) with deep forest-pine actions (`#1e4d36`) and crisp white data cards (`#ffffff`) so farmers and agronomists can inspect satellite climate anomalies, soil taxonomy, NDVI health, and crop rotation profitability without visual glare. Every metric uses tabular numerals (`Public Sans` + `tabular-nums`) and semantic `shadcn/ui` + Radix primitives so multi-channel outputs (Web dashboard, WhatsApp digest, and Mobile payload) remain scannable, accessible, and consistent.

## Colors

The palette anchors on calm agronomic neutrals tinted subtly toward sage and pine rather than sterile gray:

- **Surface-Paper Discipline**: Always set the canvas background to `--background` (`hsl(80 18% 97%)` / `#f7f9f5`) and elevated panels to pure white `--card` (`#ffffff`), keeping subtle tonal separation via `--border` (`#d3dbd0`) instead of heavy drop shadows.
- **Forest-Pine Action Anchor**: Reserve `--primary` (`hsl(150 44% 21%)` / `#1e4d36`) for primary CTAs (`Analizar rotación`, selected scenario triggers, active tab text) and never flood large background regions with saturated green.
- **Contrast-First Ink**: Maintain ≥4.5:1 text contrast using `--foreground` (`#16271d`) for primary copy and `--muted-foreground` (`#556c5d`) for units, helper descriptions, and chart axes.
- **Semantic Status Restraint**: Encode agronomic risk strictly with status tokens (`success` emerald for optimal suitability/positive balance, `warning` amber for drought/monoculture alerts, `destructive` `#c52020` for critical warnings or erosion risk). Never attach decorative `border-left` accent bars (`side-tab`) to cards or alerts.

## Typography

- **Unified Humanist Sans**: Load `@fontsource/public-sans` (`Public Sans`, fallback `system-ui, -apple-system, sans-serif`) globally across all UI controls, tooltips, charts, and channel previews.
- **Tabular Scientific Numerals**: Apply `font-variant-numeric: tabular-nums` (`tabular-nums`) to coordinates, temperatures, millimeter water deficits, slope percentages, soil texture fractions, and economic ROI values so columns align cleanly during comparison.
- **Hierarchy Without Noise**: Use concise H1/H2/H3 weights (`600`–`700`) and avoid uppercase eyebrow kickers or artificial `01/02/03` section numbering prefixes.

## Layout

- **Max-Width Workbench Container**: Center the application within `1320px` (`2xl: "1320px"`) with `1.5rem` horizontal padding and comfortable vertical breathing room (`20px`–`24px` gaps).
- **Split Decision Flow**: Organize the workspace into an interactive parcel input header (map + Nominatim place search + crop history form), a responsive telemetry grid (climate/water KPIs, soil DNA, NDVI status, Recharts trends), and a 3-column comparative rotation grid (`1fr` mobile, `3fr` desktop).
- **Instant Perceived Continuity**: Render `DashboardSkeleton` matching card footprints while asynchronous NASA POWER, SRTM, SoilGrids/SSURGO, and GIBS requests resolve.

## Elevation & Depth

- **Whisper-Quiet Card Lift**: Cards use a hairline `1px solid` border (`--border`) paired with a low-opacity pine-tinted shadow (`0 2px 10px rgba(20, 40, 28, 0.04)`).
- **Layered Radix Overlays**: Popovers, `Select` dropdowns, and explanatory `Tooltip` panels rise above Leaflet controls (`z-50`) with crisp `1px` borders so metric explanations (`ET₀`, `SMAP`, `NDVI`, `Hargreaves`) remain readable over dense charts and maps.

## Shapes

- **Measured Softness**: Use a `--radius` base of `0.625rem` (`10px`) yielding `12px` (`rounded-xl`) cards, `8px` (`rounded-md`) inputs/buttons/badges, and `9999px` pills only where explicitly circular (status indicators, legend dots).
- **Consistent Control Heights**: Standardize inputs, select triggers, and default buttons at `40px` (`h-10`), compact action buttons at `32px` (`h-8`), and hero submit CTAs at `44px` (`h-11`).

## Components

- **Button (`default`, `outline`, `secondary`)**: Solid pine green for the primary analysis action, clean bordered white for secondary tools (draw polygon, clear, WhatsApp `wa.me` share), with `150ms` hover/focus-ring transitions.
- **Card & Telemetry KPIs**: White bounded containers (`p-5`) with header title + optional `Tooltip` badge, large tabular reading, and muted single-line context.
- **Badge (`default`, `secondary`, `outline`, `success`, `warning`, `destructive`)**: Compact `px-2.5 py-0.5 text-xs font-semibold` pills displaying crop suitability tier, soil drainage class, monoculture alert, and price trend delta.
- **Inputs & Radix Select**: Daylight-clear controls with accessible `:focus-visible` pine rings (`ring-ring`) for latitude, longitude, current crop, and consecutive monoculture years.
- **Tabs & Channel Previews**: Radix `Tabs` switching between Climate & Water charts (Recharts) and Channel Output Previews (Web summary, formatted WhatsApp message, compact Mobile JSON/card).

## Do's and Don'ts

- **Do** validate and keep coordinates, climate units (`°C`, `mm`, `%`), and water balance metrics formatted with `tabular-nums`.
- **Do** surface plain-language agronomy tooltips beside technical NASA/FAO indicators (`GWETTOP`, `ET₀`, `NDVI`).
- **Do** keep map controls, search results, and skeleton loaders responsive across mobile and desktop viewports.
- **Don't** add thick `4px` `border-left` colored stripes (`side-tab` pattern) to cards, alerts, or recommendation columns.
- **Don't** inject neon purples, dark-mode telemetry walls, or unrequested `Inter` font defaults.
- **Don't** mix raw inline CSS overrides with `shadcn/ui` utility tokens for core interactive primitives.
