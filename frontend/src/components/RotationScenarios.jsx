import React, { useState } from "react";
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  Legend,
} from "recharts";
import {
  ArrowRight,
  Calendar,
  Check,
  ChevronDown,
  Copy,
  DollarSign,
  Leaf,
  Lightbulb,
  Repeat,
  Share2,
  Sprout,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

const MONTHS_META = [
  { num: 1, short: "E", abbr: "ene", full: "enero" },
  { num: 2, short: "F", abbr: "feb", full: "febrero" },
  { num: 3, short: "M", abbr: "mar", full: "marzo" },
  { num: 4, short: "A", abbr: "abr", full: "abril" },
  { num: 5, short: "M", abbr: "may", full: "mayo" },
  { num: 6, short: "J", abbr: "jun", full: "junio" },
  { num: 7, short: "J", abbr: "jul", full: "julio" },
  { num: 8, short: "A", abbr: "ago", full: "agosto" },
  { num: 9, short: "S", abbr: "sep", full: "septiembre" },
  { num: 10, short: "O", abbr: "oct", full: "octubre" },
  { num: 11, short: "N", abbr: "nov", full: "noviembre" },
  { num: 12, short: "D", abbr: "dic", full: "diciembre" },
];

const RADAR_COLORS = ["#1e4d36", "#0284c7", "#d97706"];

function riskBadgeVariant(risk) {
  if (risk === "Bajo") return "success";
  if (risk === "Moderado") return "warning";
  return "destructive";
}

function buildRadarData(scenarios) {
  if (!scenarios || scenarios.length === 0 || !scenarios[0].score_breakdown) return [];
  const axes = Object.keys(scenarios[0].score_breakdown);
  return axes.map((axis) => {
    const point = { axis };
    scenarios.forEach((sc, idx) => {
      point[`opt${idx + 1}`] = sc.score_breakdown?.[axis] ?? 50;
    });
    return point;
  });
}

function MonthStrip({ sowingWindow, frostMonths = [], dryMonths = [] }) {
  const sowNorm = (sowingWindow || "").toLowerCase();
  const frostSet = new Set(frostMonths.map((m) => m.toLowerCase()));
  const drySet = new Set(dryMonths.map((m) => m.toLowerCase()));

  return (
    <div className="space-y-1.5 rounded-lg border bg-muted/20 p-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-muted-foreground">
        <span className="font-semibold text-foreground">Calendario anual (12 meses)</span>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-sm bg-emerald-600" /> Siembra
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-sm bg-sky-300" /> Helada
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-sm bg-amber-300" /> Seco
          </span>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-1">
        {MONTHS_META.map((m) => {
          const isSow = sowNorm.includes(m.full);
          const isFrost = frostSet.has(m.abbr);
          const isDry = drySet.has(m.abbr);

          let cellClass = "border bg-card text-muted-foreground";
          let title = `${m.full}: neutro`;
          if (isSow) {
            cellClass = "border-emerald-700 bg-emerald-600 font-bold text-white";
            title = `${m.full}: ventana ideal de siembra`;
          } else if (isFrost) {
            cellClass = "border-sky-300 bg-sky-100 font-semibold text-sky-900";
            title = `${m.full}: riesgo de heladas`;
          } else if (isDry) {
            cellClass = "border-amber-300 bg-amber-100 font-semibold text-amber-900";
            title = `${m.full}: humedad SMAP baja (<45%)`;
          }

          return (
            <div
              key={m.num}
              title={title}
              className={`flex h-6 items-center justify-center rounded text-[11px] tabular-nums ${cellClass}`}
            >
              {m.short}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function RotationScenarios({
  scenarios,
  currentCrop,
  anomalies,
  hectares = 1,
  whatsappShareText,
}) {
  const [copied, setCopied] = useState(false);
  const [expandedFit, setExpandedFit] = useState({});

  const effectiveHa = Number(hectares) > 0 ? Number(hectares) : 1;
  const radarData = buildRadarData(scenarios);
  const shareUrl = whatsappShareText
    ? `https://wa.me/?text=${encodeURIComponent(whatsappShareText)}`
    : null;

  const handleCopySummary = async () => {
    if (!whatsappShareText) return;
    try {
      await navigator.clipboard.writeText(whatsappShareText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  const toggleFit = (cropId) => {
    setExpandedFit((prev) => ({ ...prev, [cropId]: !prev[cropId] }));
  };

  return (
    <Card>
      <CardHeader className="pb-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2">
              <Sprout className="h-5 w-5 text-primary" />
              Tres escenarios comparativos de rotación tras {currentCrop.name}
            </CardTitle>
            <CardDescription>
              Comparativa agronómica y económica calculada para{" "}
              <span className="font-semibold text-foreground tabular-nums">{effectiveHa} ha</span>.
            </CardDescription>
          </div>

          <div className="no-print flex flex-wrap gap-2">
            {whatsappShareText && (
              <Button type="button" variant="outline" size="sm" onClick={handleCopySummary}>
                {copied ? <Check className="h-4 w-4 text-emerald-700" /> : <Copy className="h-4 w-4" />}
                {copied ? "Copiado" : "Copiar resumen"}
              </Button>
            )}
            {shareUrl && (
              <Button asChild variant="outline" size="sm">
                <a href={shareUrl} target="_blank" rel="noreferrer">
                  <Share2 className="h-4 w-4" />
                  Compartir por WhatsApp
                </a>
              </Button>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {radarData.length > 0 && (
          <div className="print-avoid-break rounded-xl border bg-muted/20 p-4">
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h4 className="text-sm font-semibold text-foreground">
                Comparativa visual 5 ejes (Clima, Suelo, Relieve, Regeneración y Rentabilidad)
              </h4>
              <span className="text-xs text-muted-foreground">Puntaje normalizado 0–100 por pilar</span>
            </div>
            <ResponsiveContainer width="100%" height={260}>
              <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="74%">
                <PolarGrid stroke="#cbd5e1" />
                <PolarAngleAxis dataKey="axis" tick={{ fontSize: 12, fill: "#1d3528" }} />
                <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 10 }} />
                {scenarios.map((sc, idx) => (
                  <Radar
                    key={sc.crop_id}
                    name={`Opción ${sc.scenario_rank}: ${sc.crop_name}`}
                    dataKey={`opt${idx + 1}`}
                    stroke={RADAR_COLORS[idx % RADAR_COLORS.length]}
                    fill={RADAR_COLORS[idx % RADAR_COLORS.length]}
                    fillOpacity={idx === 0 ? 0.24 : 0.12}
                    strokeWidth={2}
                  />
                ))}
                <Legend wrapperStyle={{ fontSize: "12px" }} />
                <ChartTooltip />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        )}

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
          {scenarios.map((sc) => {
            const isExpanded = Boolean(expandedFit[sc.crop_id]);
            const scorePct = Math.max(0, Math.min(100, sc.suitability_score));
            const totalMargin = Math.round(sc.economics.estimated_margin_usd_ha * effectiveHa);
            const totalNSavings = Math.round(sc.economics.fertilizer_savings_usd_ha * effectiveHa);

            return (
              <div
                key={sc.crop_id}
                className={`print-avoid-break flex flex-col justify-between gap-4 rounded-xl border bg-card p-5 transition-shadow hover:shadow-md ${
                  sc.scenario_rank === 1 ? "border-primary/60 ring-1 ring-primary/20" : ""
                }`}
              >
                <div className="space-y-3.5">
                  <div className="flex items-center justify-between gap-2">
                    <Badge variant={sc.scenario_rank === 1 ? "default" : "secondary"}>
                      Opción {sc.scenario_rank}
                    </Badge>
                    <div className="flex items-center gap-1.5">
                      <Badge variant={riskBadgeVariant(sc.risk_level)}>Riesgo {sc.risk_level}</Badge>
                      <span className="rounded-md bg-muted px-2 py-0.5 text-xs font-bold tabular-nums text-foreground">
                        {sc.suitability_score.toFixed(0)}/100
                      </span>
                    </div>
                  </div>

                  <div>
                    <p className="text-xs font-medium text-muted-foreground">{sc.strategy_name}</p>
                    <h4 className="mt-0.5 text-2xl font-bold tracking-tight text-foreground">
                      {sc.crop_name}
                    </h4>
                    <p className="text-xs text-muted-foreground">
                      <em>{sc.scientific_name}</em> · {sc.category} · Ciclo ~{sc.cycle_days} días
                    </p>
                    <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full bg-primary transition-all duration-300"
                        style={{ width: `${scorePct}%` }}
                      />
                    </div>
                  </div>

                  <Badge variant="success" className="w-fit py-1 text-xs">
                    <Calendar className="h-3.5 w-3.5" />
                    Siembra ideal: {sc.sowing_window}
                  </Badge>

                  <MonthStrip
                    sowingWindow={sc.sowing_window}
                    frostMonths={anomalies?.frost_risk_months}
                    dryMonths={anomalies?.dry_soil_months}
                  />

                  <div className="grid grid-cols-2 gap-2 rounded-lg border bg-muted/25 p-2.5 text-xs tabular-nums">
                    <div>
                      <span className="text-muted-foreground">Total ({effectiveHa} ha)</span>
                      <div className="font-bold text-foreground">
                        USD {totalMargin.toLocaleString("es-ES")}
                      </div>
                      <span className="text-[11px] text-muted-foreground">
                        USD {Math.round(sc.economics.estimated_margin_usd_ha)}/ha
                      </span>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Mercado & N</span>
                      <div className="font-bold text-foreground">
                        USD {Math.round(sc.economics.price_usd_ton)}/t (
                        {sc.economics.yoy_trend_pct >= 0 ? "+" : ""}
                        {sc.economics.yoy_trend_pct.toFixed(1)}%)
                      </div>
                      <span className="text-[11px] text-emerald-800">
                        {totalNSavings > 0
                          ? `Ahorro N: USD ${totalNSavings.toLocaleString("es-ES")}`
                          : "Sin fijación neta N"}
                      </span>
                    </div>
                  </div>

                  <div className="rounded-lg border border-sky-200 bg-sky-50/70 p-3">
                    <div className="mb-1 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-sky-900">
                      <Lightbulb className="h-3.5 w-3.5" />
                      Por qué se sugiere esta planta
                    </div>
                    <p className="text-sm leading-relaxed text-sky-950">{sc.why_suggested}</p>
                  </div>

                  <div className="rounded-lg border border-emerald-200 bg-emerald-50/70 p-3">
                    <div className="mb-1 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-emerald-900">
                      <Leaf className="h-3.5 w-3.5" />
                      Qué beneficios traerá a tu suelo
                    </div>
                    <p className="text-sm leading-relaxed text-emerald-950">{sc.soil_benefits}</p>
                  </div>

                  <div className="rounded-lg border border-amber-200 bg-amber-50/70 p-3">
                    <div className="mb-1 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-amber-900">
                      <DollarSign className="h-3.5 w-3.5" />
                      Rentabilidad y mercado
                    </div>
                    <p className="text-xs leading-relaxed text-amber-950 tabular-nums">
                      {sc.economics.economic_summary}
                    </p>
                  </div>

                  <div className="rounded-lg border bg-muted/30 p-3">
                    <div className="mb-2 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide text-foreground">
                      <Repeat className="h-3.5 w-3.5 text-primary" />
                      Flujo sugerido (3 campañas)
                    </div>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                      {sc.rotation_sequence.map((step, stepIdx) => (
                        <div
                          key={step.campaign}
                          className="relative flex flex-col justify-between rounded-md border bg-card p-2 text-xs"
                        >
                          <div className="flex items-center justify-between gap-1">
                            <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[11px] font-bold text-primary-foreground tabular-nums">
                              {step.campaign}
                            </span>
                            {stepIdx < sc.rotation_sequence.length - 1 && (
                              <ArrowRight className="hidden h-3.5 w-3.5 text-muted-foreground sm:inline" />
                            )}
                          </div>
                          <div className="mt-1 font-bold text-foreground">{step.crop_name}</div>
                          <div className="text-[11px] leading-tight text-muted-foreground">{step.role}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="space-y-2 pt-1">
                  <Separator />
                  <button
                    type="button"
                    onClick={() => toggleFit(sc.crop_id)}
                    className="no-print flex w-full items-center justify-between py-1 text-xs font-semibold text-primary hover:underline"
                  >
                    <span>Ficha técnica (suelo, clima, heladas, relieve)</span>
                    <ChevronDown
                      className={`h-4 w-4 transition-transform duration-150 ${
                        isExpanded ? "rotate-180" : ""
                      }`}
                    />
                  </button>
                  {isExpanded && (
                    <div className="space-y-1 text-xs text-muted-foreground">
                      <p>
                        <strong className="text-foreground">Suelo y pH:</strong> {sc.soil_fit}
                      </p>
                      <p>
                        <strong className="text-foreground">Clima y agua:</strong> {sc.climate_fit}
                      </p>
                      <p>
                        <strong className="text-foreground">Heladas:</strong> {sc.frost_fit}
                      </p>
                      <p>
                        <strong className="text-foreground">Topografía:</strong> {sc.slope_fit}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
