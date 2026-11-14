import React from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AlertTriangle,
  CloudRain,
  Droplets,
  HelpCircle,
  Layers,
  Mountain,
  Sprout,
  Thermometer,
  TrendingUp,
} from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

function MetricLabel({ icon: Icon, label, hint }) {
  return (
    <div className="flex items-center justify-between gap-1 text-xs font-medium text-muted-foreground">
      <span className="inline-flex items-center gap-1.5">
        <Icon className="h-3.5 w-3.5 text-primary" />
        {label}
      </span>
      {hint && (
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              className="rounded-full p-0.5 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label={`Explicación de ${label}`}
            >
              <HelpCircle className="h-3.5 w-3.5" />
            </button>
          </TooltipTrigger>
          <TooltipContent>{hint}</TooltipContent>
        </Tooltip>
      )}
    </div>
  );
}

export default function ClimateDashboard({
  climate,
  terrain,
  soil,
  vegetation,
  scenarios = [],
}) {
  const { anomalies, annual_series, monthly_climatology } = climate;
  const smapPct = Math.round(anomalies.avg_soil_wetness_top * 100);
  const economicsChartData = scenarios.map((sc) => ({
    crop: sc.crop_name,
    margin: Math.round(sc.economics.estimated_margin_usd_ha),
    n_savings: Math.round(sc.economics.fertilizer_savings_usd_ha),
  }));

  return (
    <Card>
      <CardHeader className="pb-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-primary" />
              Diagnóstico satelital del lote
            </CardTitle>
            <CardDescription>
              Período reciente ({anomalies.recent_period}) frente a histórico ({anomalies.baseline_period}) con foco en{" "}
              <span className="font-semibold text-foreground">{anomalies.seasonal_focus_label}</span>.
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <Badge variant="secondary">Zona {anomalies.climate_zone}</Badge>
            <Badge variant="outline">
              {terrain.source.startsWith("nasa_srtm_90m") ? "SRTM 90m" : "Relieve estimado"}
            </Badge>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-5">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div className="rounded-lg border bg-muted/25 p-3.5">
            <MetricLabel
              icon={Thermometer}
              label="Temperatura y heladas"
              hint="Media anual de NASA POWER y temperatura mínima media del mes más frío para evaluar riesgo de heladas."
            />
            <div className="mt-1.5 flex items-baseline justify-between gap-2">
              <span className="text-2xl font-bold tabular-nums">
                {anomalies.recent_avg_temp_c.toFixed(1)} °C
              </span>
              <Badge variant={anomalies.hotter_recent_trend ? "warning" : "secondary"} className="tabular-nums">
                {anomalies.temp_anomaly_c >= 0 ? "+" : ""}
                {anomalies.temp_anomaly_c.toFixed(1)} °C
              </Badge>
            </div>
            <p className="mt-1 text-xs text-muted-foreground tabular-nums">
              {anomalies.seasonal_focus_label}: {anomalies.summer_temp_anomaly_c >= 0 ? "+" : ""}
              {anomalies.summer_temp_anomaly_c.toFixed(1)} °C · Mín. fría {anomalies.min_temp_coldest_month_c.toFixed(1)} °C
            </p>
          </div>

          <div className="rounded-lg border bg-muted/25 p-3.5">
            <MetricLabel
              icon={CloudRain}
              label="Lluvia vs. ET₀"
              hint="Precipitación anual frente a evapotranspiración de referencia (ET₀). Un balance negativo indica mayor necesidad de cultivos resistentes a sequía."
            />
            <div className="mt-1.5 flex items-baseline justify-between gap-2">
              <span className="text-2xl font-bold tabular-nums">
                {Math.round(anomalies.recent_annual_rain_mm)} mm
              </span>
              <Badge variant={anomalies.water_balance_mm < -150 ? "warning" : "success"} className="tabular-nums">
                {anomalies.water_balance_mm >= 0 ? "+" : ""}
                {Math.round(anomalies.water_balance_mm)} mm
              </Badge>
            </div>
            <p className="mt-1 text-xs text-muted-foreground tabular-nums">
              ET₀ {Math.round(anomalies.annual_et0_mm)} mm · Variación {anomalies.rain_anomaly_pct >= 0 ? "+" : ""}
              {anomalies.rain_anomaly_pct.toFixed(0)}%
              {anomalies.max_daily_rain_mm > 0
                ? ` · Pico ${anomalies.max_daily_rain_mm.toFixed(0)} mm/d (${anomalies.extreme_rain_days_gt40mm} tormentas >40mm)`
                : ""}
            </p>
          </div>

          <div className="rounded-lg border bg-muted/25 p-3.5">
            <MetricLabel
              icon={Droplets}
              label="Humedad suelo (SMAP)"
              hint="Fracción de humedad superficial (0–5 cm) y radicular asimilada de NASA SMAP/POWER. Por debajo de 45% indica estrés hídrico."
            />
            <div className="mt-1.5 flex items-baseline justify-between gap-2">
              <span className="text-2xl font-bold tabular-nums">{smapPct} %</span>
              <Badge variant={smapPct < 45 ? "warning" : "success"}>
                {smapPct < 45 ? "Déficit" : "Adecuada"}
              </Badge>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Raíz {Math.round(anomalies.avg_soil_wetness_root * 100)}% ·{" "}
              {anomalies.dry_soil_months.length > 0
                ? `Baja en ${anomalies.dry_soil_months.join(", ")}`
                : "Sin meses secos críticos"}
            </p>
          </div>

          <div className="rounded-lg border bg-muted/25 p-3.5">
            <MetricLabel
              icon={Mountain}
              label="Pendiente y relieve SRTM"
              hint="Pendiente calculada con elevaciones NASA SRTM 90m. Pendientes altas exigen raíces profundas o cobertura vegetal."
            />
            <div className="mt-1.5 flex items-baseline justify-between gap-2">
              <span className="text-2xl font-bold tabular-nums">
                {terrain.slope_pct.toFixed(1)} %
                {terrain.area_ha !== null && terrain.area_ha !== undefined && (
                  <span className="ml-1.5 text-base font-semibold text-primary">· {terrain.area_ha} ha</span>
                )}
              </span>
              <Badge
                variant={
                  terrain.erosion_risk === "Bajo"
                    ? "success"
                    : terrain.erosion_risk === "Moderado"
                    ? "warning"
                    : "destructive"
                }
              >
                Erosión {terrain.erosion_risk}
              </Badge>
            </div>
            <p className="mt-1 text-xs text-muted-foreground tabular-nums">
              {terrain.terrain_class} · {Math.round(terrain.min_elevation_m)}–{Math.round(terrain.max_elevation_m)} m
            </p>
          </div>

          <div className="rounded-lg border bg-muted/25 p-3.5">
            <MetricLabel
              icon={Layers}
              label="Suelo (SoilGrids / SSURGO)"
              hint="Acidez (pH), carbono orgánico (SOC) y textura USDA (0–15 cm) para verificar compatibilidad química y drenaje."
            />
            <div className="mt-1.5 flex items-baseline justify-between gap-2">
              <span className="text-2xl font-bold tabular-nums">pH {soil.ph_h2o.toFixed(1)}</span>
              <Badge variant="outline" className="tabular-nums">
                SOC {soil.soc_g_kg.toFixed(1)} g/kg
              </Badge>
            </div>
            <div className="mt-2 space-y-1">
              <div className="flex h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                  style={{ width: `${soil.clay_pct}%` }}
                  className="bg-amber-700"
                  title={`Arcilla ${soil.clay_pct}%`}
                />
                <div
                  style={{ width: `${soil.silt_pct}%` }}
                  className="bg-emerald-600"
                  title={`Limo ${soil.silt_pct}%`}
                />
                <div
                  style={{ width: `${soil.sand_pct}%` }}
                  className="bg-amber-300"
                  title={`Arena ${soil.sand_pct}%`}
                />
              </div>
              <p className="text-[11px] text-muted-foreground tabular-nums">
                {soil.texture_class} (Arc {soil.clay_pct}% · Lim {soil.silt_pct}% · Are {soil.sand_pct}%)
                {soil.usda_ssurgo_mapunit ? ` · USDA: ${soil.usda_ssurgo_mapunit}` : ""}
              </p>
            </div>
          </div>

          <div className="rounded-lg border bg-muted/25 p-3.5">
            <MetricLabel
              icon={Sprout}
              label="Vigor vegetal (NDVI)"
              hint="Índice de verdor estimado (0–1) y nivel de riesgo por monocultivo consecutivo."
            />
            <div className="mt-1.5 flex items-baseline justify-between gap-2">
              <span className="text-2xl font-bold tabular-nums">
                NDVI {vegetation.estimated_ndvi.toFixed(2)}
              </span>
              <Badge
                variant={
                  vegetation.soil_exhaustion_risk === "Bajo"
                    ? "success"
                    : vegetation.soil_exhaustion_risk === "Moderado"
                    ? "warning"
                    : "destructive"
                }
              >
                Agotamiento {vegetation.soil_exhaustion_risk}
              </Badge>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">{vegetation.ndvi_status}</p>
            {vegetation.cdl_history && vegetation.cdl_history.length > 0 && (
              <div className="mt-1.5 flex flex-wrap gap-1">
                {vegetation.cdl_history.map((item) => (
                  <Badge key={item.year} variant="outline" className="text-[10px] tabular-nums">
                    CDL {item.year}: {item.category}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="space-y-2">
          {anomalies.climate_alerts.map((alert, idx) => (
            <Alert key={idx} variant="warning">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-700" />
              <AlertDescription>{alert}</AlertDescription>
            </Alert>
          ))}
          <Alert variant={vegetation.soil_exhaustion_risk === "Alto" ? "warning" : "success"}>
            <Sprout className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" />
            <AlertDescription>{vegetation.vegetation_alert}</AlertDescription>
          </Alert>
        </div>

        <Tabs defaultValue="annual" className="w-full">
          <TabsList className="flex-wrap">
            <TabsTrigger value="annual">Tendencia anual (11 años)</TabsTrigger>
            <TabsTrigger value="monthly">Climatología mensual (Lluvia, ET₀ y SMAP)</TabsTrigger>
            {vegetation.ndvi_series && vegetation.ndvi_series.length > 0 && (
              <TabsTrigger value="ndvi">Vigor NDVI ({vegetation.ndvi_series.length} pts)</TabsTrigger>
            )}
            {vegetation.ndvi_series && vegetation.ndvi_series.length > 0 && (
            <TabsContent value="ndvi">
              <div className="rounded-lg border bg-card p-4">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <h4 className="text-sm font-semibold text-foreground">
                    Evolución reciente del índice de verdor (NDVI 0–1)
                  </h4>
                  <Badge variant="outline" className="text-xs">
                    {vegetation.source.includes("ornl_modis")
                      ? "NASA ORNL MODIS MOD13Q1 (250 m)"
                      : "Modelo NDVI SMAP/NASA POWER"}
                  </Badge>
                </div>
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={vegetation.ndvi_series}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="date" fontSize={11} />
                    <YAxis fontSize={12} domain={[0, 1]} />
                    <ChartTooltip />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="ndvi"
                      name="NDVI (0–1)"
                      stroke="#15803d"
                      strokeWidth={2.5}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </TabsContent>
          )}

          {economicsChartData.length > 0 && (
              <TabsTrigger value="economics">Margen y ahorro N (USD/ha)</TabsTrigger>
            )}
          </TabsList>

          <TabsContent value="annual">
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div className="rounded-lg border bg-card p-4">
                <h4 className="mb-3 text-sm font-semibold text-foreground">
                  Temperatura anual y {anomalies.seasonal_focus_label} (°C)
                </h4>
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={annual_series}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="year" fontSize={12} />
                    <YAxis fontSize={12} unit="°" />
                    <ChartTooltip />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="avg_temp_c"
                      name="Media anual (°C)"
                      stroke="#1e4d36"
                      strokeWidth={2.25}
                      dot={{ r: 3 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="summer_avg_temp_c"
                      name={`${anomalies.seasonal_focus_label} (°C)`}
                      stroke="#d97706"
                      strokeWidth={2.25}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div className="rounded-lg border bg-card p-4">
                <h4 className="mb-3 text-sm font-semibold text-foreground">
                  Precipitación anual vs. demanda atmosférica ET₀ (mm)
                </h4>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={annual_series}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="year" fontSize={12} />
                    <YAxis fontSize={12} unit=" mm" />
                    <ChartTooltip />
                    <Legend />
                    <Bar dataKey="total_rain_mm" name="Lluvia anual (mm)" fill="#2563eb" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="total_et0_mm" name="ET₀ anual (mm)" fill="#d97706" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="monthly">
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <div className="rounded-lg border bg-card p-4">
                <h4 className="mb-3 text-sm font-semibold text-foreground">
                  Balance hídrico mensual: lluvia vs. ET₀ (mm)
                </h4>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={monthly_climatology}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="month_name" fontSize={12} />
                    <YAxis fontSize={12} unit=" mm" />
                    <ChartTooltip />
                    <Legend />
                    <Bar dataKey="avg_rain_mm" name="Lluvia promedio (mm)" fill="#2563eb" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="avg_et0_mm" name="ET₀ promedio (mm)" fill="#d97706" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="rounded-lg border bg-card p-4">
                <h4 className="mb-3 text-sm font-semibold text-foreground">
                  Humedad superficial SMAP (0–1) y T° mínima mensual (°C)
                </h4>
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={monthly_climatology}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="month_name" fontSize={12} />
                    <YAxis yAxisId="left" fontSize={12} domain={[0, 1]} />
                    <YAxis yAxisId="right" orientation="right" fontSize={12} unit="°" />
                    <ChartTooltip />
                    <Legend />
                    <Line
                      yAxisId="left"
                      type="monotone"
                      dataKey="avg_soil_wetness_top"
                      name="Humedad suelo SMAP"
                      stroke="#0d9488"
                      strokeWidth={2.25}
                    />
                    <Line
                      yAxisId="right"
                      type="monotone"
                      dataKey="avg_temp_min_c"
                      name="T° mínima media (°C)"
                      stroke="#0284c7"
                      strokeWidth={2.25}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </TabsContent>

          {vegetation.ndvi_series && vegetation.ndvi_series.length > 0 && (
            <TabsContent value="ndvi">
              <div className="rounded-lg border bg-card p-4">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <h4 className="text-sm font-semibold text-foreground">
                    Evolución reciente del índice de verdor (NDVI 0–1)
                  </h4>
                  <Badge variant="outline" className="text-xs">
                    {vegetation.source.includes("ornl_modis")
                      ? "NASA ORNL MODIS MOD13Q1 (250 m)"
                      : "Modelo NDVI SMAP/NASA POWER"}
                  </Badge>
                </div>
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={vegetation.ndvi_series}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="date" fontSize={11} />
                    <YAxis fontSize={12} domain={[0, 1]} />
                    <ChartTooltip />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="ndvi"
                      name="NDVI (0–1)"
                      stroke="#15803d"
                      strokeWidth={2.5}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </TabsContent>
          )}

          {economicsChartData.length > 0 && (
            <TabsContent value="economics">
              <div className="rounded-lg border bg-card p-4">
                <h4 className="mb-3 text-sm font-semibold text-foreground">
                  Margen neto estimado y ahorro en fertilizante nitrogenado por escenario (USD/ha)
                </h4>
                <ResponsiveContainer width="100%" height={240}>
                  <BarChart data={economicsChartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="crop" fontSize={12} />
                    <YAxis fontSize={12} unit=" $" />
                    <ChartTooltip />
                    <Legend />
                    <Bar dataKey="margin" name="Margen neto est. (USD/ha)" fill="#1e4d36" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="n_savings" name="Ahorro urea/N (USD/ha)" fill="#059669" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </TabsContent>
          )}
        </Tabs>
      </CardContent>
    </Card>
  );
}
