import React from "react";
import { Award, Calendar, Droplets, Layers, Mountain, Printer, Share2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

function statusDotClass(level) {
  if (level === "good") return "bg-emerald-600";
  if (level === "warn") return "bg-amber-500";
  return "bg-red-600";
}

function evaluateWaterLight(anomalies) {
  const smap = anomalies.avg_soil_wetness_top * 100;
  if (anomalies.water_balance_mm < -350 || smap < 35) {
    return {
      level: "risk",
      title: "Estrés hídrico marcado",
      detail: `Balance ${Math.round(anomalies.water_balance_mm)} mm/año y humedad SMAP ${Math.round(smap)}%. Priorizá cultivos rústicos o de ciclo corto.`,
    };
  }
  if (anomalies.water_balance_mm < -120 || anomalies.drier_recent_trend || smap < 50) {
    return {
      level: "warn",
      title: "Humedad estacional ajustada",
      detail: `Balance ${Math.round(anomalies.water_balance_mm)} mm/año; conviene optimizar ventana de siembra según SMAP (${Math.round(smap)}%).`,
    };
  }
  return {
    level: "good",
    title: "Disponibilidad hídrica favorable",
    detail: `Lluvia ${Math.round(anomalies.recent_annual_rain_mm)} mm/año y humedad superficial SMAP del ${Math.round(smap)}%.`,
  };
}

function evaluateSoilLight(soil) {
  if (soil.ph_h2o < 5.2 || soil.ph_h2o > 8.2) {
    return {
      level: "risk",
      title: `pH ${soil.ph_h2o.toFixed(1)} restrictivo`,
      detail: `${soil.texture_class} (${soil.ph_class.toLowerCase()}); requiere especies tolerantes o corrección previa.`,
    };
  }
  if (soil.ph_h2o < 5.8 || soil.ph_h2o > 7.5 || soil.drainage_class.includes("Lento")) {
    return {
      level: "warn",
      title: `Suelo ${soil.texture_class} · ${soil.ph_class}`,
      detail: `pH ${soil.ph_h2o.toFixed(1)} con drenaje ${soil.drainage_class.toLowerCase()}.`,
    };
  }
  return {
    level: "good",
    title: `Suelo equilibrado (${soil.texture_class})`,
    detail: `pH ${soil.ph_h2o.toFixed(1)} óptimo agrícola y drenaje ${soil.drainage_class.toLowerCase()}.`,
  };
}

function evaluatePlotRiskLight(terrain, vegetation) {
  if (vegetation.soil_exhaustion_risk === "Alto" || terrain.erosion_risk === "Alto" || terrain.erosion_risk === "Crítico") {
    return {
      level: "risk",
      title: `Alerta: agotamiento ${vegetation.soil_exhaustion_risk.toLowerCase()} / erosión ${terrain.erosion_risk.toLowerCase()}`,
      detail: `Pendiente ${terrain.slope_pct.toFixed(1)}% tras ${vegetation.monoculture_years} campaña(s); urge cambio de familia y cobertura radicular.`,
    };
  }
  if (vegetation.soil_exhaustion_risk === "Moderado" || terrain.erosion_risk === "Moderado") {
    return {
      level: "warn",
      title: "Rotación recomendada este ciclo",
      detail: `Pendiente ${terrain.slope_pct.toFixed(1)}% (${terrain.terrain_class}); alternar cultivo mantiene vigor NDVI (${vegetation.estimated_ndvi.toFixed(2)}).`,
    };
  }
  return {
    level: "good",
    title: "Lote estable para diversificar",
    detail: `Pendiente suave (${terrain.slope_pct.toFixed(1)}%) y bajo agotamiento tras la última campaña.`,
  };
}

export default function VerdictBanner({
  result,
  hectares,
  whatsappShareText,
}) {
  const top = result?.scenarios?.[0];
  if (!top) return null;

  const water = evaluateWaterLight(result.climate_analysis.anomalies);
  const soilLight = evaluateSoilLight(result.soil_profile);
  const plotRisk = evaluatePlotRiskLight(result.terrain_analysis, result.vegetation_health);
  const effectiveHa = Number(hectares) > 0 ? Number(hectares) : 1;
  const totalMargin = Math.round(top.economics.estimated_margin_usd_ha * effectiveHa);
  const totalSavings = Math.round(top.economics.fertilizer_savings_usd_ha * effectiveHa);
  const shareUrl = whatsappShareText
    ? `https://wa.me/?text=${encodeURIComponent(whatsappShareText)}`
    : null;

  return (
    <Card className="print-avoid-break border-primary/35 bg-card">
      <CardContent className="space-y-4 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="default">
                <Award className="h-3.5 w-3.5" />
                Mejor recomendación tras {result.current_crop.name}
              </Badge>
              <Badge variant="success">
                <Calendar className="h-3.5 w-3.5" />
                Siembra ideal: {top.sowing_window}
              </Badge>
              <Badge variant="outline" className="tabular-nums">
                Puntaje {top.suitability_score.toFixed(0)}/100
              </Badge>
            </div>
            <h2 className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
              {top.crop_name}
              <span className="ml-2 text-base font-medium text-muted-foreground tabular-nums">
                · Margen est. USD {totalMargin.toLocaleString("es-ES")} ({effectiveHa} ha)
                {totalSavings > 0 ? ` · Ahorro N: USD ${totalSavings.toLocaleString("es-ES")}` : ""}
              </span>
            </h2>
            <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">
              {top.why_suggested}
            </p>
          </div>

          <div className="no-print flex flex-wrap gap-2">
            <Button type="button" variant="outline" size="sm" onClick={() => window.print()}>
              <Printer className="h-4 w-4" />
              Imprimir / PDF
            </Button>
            {shareUrl && (
              <Button asChild size="sm">
                <a href={shareUrl} target="_blank" rel="noreferrer">
                  <Share2 className="h-4 w-4" />
                  Enviar por WhatsApp
                </a>
              </Button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <div className="rounded-lg border bg-muted/25 p-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
              <span className={`h-2.5 w-2.5 rounded-full ${statusDotClass(water.level)}`} />
              <Droplets className="h-3.5 w-3.5 text-primary" />
              {water.title}
            </div>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{water.detail}</p>
          </div>

          <div className="rounded-lg border bg-muted/25 p-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
              <span className={`h-2.5 w-2.5 rounded-full ${statusDotClass(soilLight.level)}`} />
              <Layers className="h-3.5 w-3.5 text-primary" />
              {soilLight.title}
            </div>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{soilLight.detail}</p>
          </div>

          <div className="rounded-lg border bg-muted/25 p-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
              <span className={`h-2.5 w-2.5 rounded-full ${statusDotClass(plotRisk.level)}`} />
              <Mountain className="h-3.5 w-3.5 text-primary" />
              {plotRisk.title}
            </div>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{plotRisk.detail}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
