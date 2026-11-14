import React, { useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Database,
  Globe,
  Loader2,
  MapPin,
  MessageCircle,
  Satellite,
  Smartphone,
  Sparkles,
  Sprout,
  Wheat,
} from "lucide-react";
import { fetchCrops, recommendRotation } from "@/api/client";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TooltipProvider } from "@/components/ui/tooltip";
import PlotMap from "@/components/PlotMap";
import VerdictBanner from "@/components/VerdictBanner";
import ClimateDashboard from "@/components/ClimateDashboard";
import RotationScenarios from "@/components/RotationScenarios";
import ChannelPreview from "@/components/ChannelPreview";
import DashboardSkeleton from "@/components/DashboardSkeleton";

const FALLBACK_CROPS = [
  { id: "maiz", name: "Maíz", category: "Cereal" },
  { id: "trigo", name: "Trigo", category: "Cereal" },
  { id: "sorgo", name: "Sorgo", category: "Cereal rústico" },
  { id: "alfalfa", name: "Alfalfa", category: "Leguminosa forrajera" },
  { id: "soja", name: "Soja", category: "Leguminosa oleaginosa" },
  { id: "frijol", name: "Frijol / Poroto", category: "Leguminosa de grano" },
  { id: "girasol", name: "Girasol", category: "Oleaginosa" },
  { id: "garbanzo", name: "Garbanzo", category: "Leguminosa rústica" },
];

const QUICK_EXAMPLES = [
  {
    label: "Córdoba (Maíz · 2 años)",
    lat: -31.48,
    lon: -63.55,
    crop: "maiz",
    years: "2",
    ha: 35,
  },
  {
    label: "Iowa EE.UU. (Maíz · 3 años SSURGO)",
    lat: 41.9,
    lon: -93.6,
    crop: "maiz",
    years: "3",
    ha: 50,
  },
  {
    label: "Boyacá Col (Trigo · ladera)",
    lat: 5.58,
    lon: -73.3,
    crop: "trigo",
    years: "1",
    ha: 8,
  },
];

const HISTORY_STORAGE_KEY = "agronasa_recent_plots_v1";

function formatSourceTag(src = "") {
  if (src.includes("cache")) return "Caché SQLite";
  if (src.includes("fallback")) return "Respaldo offline";
  return "Satélite en vivo";
}

function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.slice(0, 5) : [];
  } catch {
    return [];
  }
}

export default function App() {
  const [lat, setLat] = useState(-31.48);
  const [lon, setLon] = useState(-63.55);
  const [plotLabel, setPlotLabel] = useState("");
  const [hectares, setHectares] = useState(25);
  const [polygon, setPolygon] = useState([]);
  const [crops, setCrops] = useState(FALLBACK_CROPS);
  const [currentCrop, setCurrentCrop] = useState("maiz");
  const [yearsSameCrop, setYearsSameCrop] = useState("1");
  const [recentPlots, setRecentPlots] = useState(() => loadHistory());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => {
    fetchCrops()
      .then((list) => {
        if (Array.isArray(list) && list.length > 0) {
          setCrops(list);
        }
      })
      .catch(() => {});
  }, []);

  const savePlotToHistory = (entry) => {
    setRecentPlots((prev) => {
      const deduped = prev.filter(
        (item) =>
          !(Math.abs(item.lat - entry.lat) < 0.01 && Math.abs(item.lon - entry.lon) < 0.01 && item.crop === entry.crop)
      );
      const next = [entry, ...deduped].slice(0, 5);
      try {
        localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(next));
      } catch {
        // Ignore storage quota errors
      }
      return next;
    });
  };

  const runAnalysis = async (params) => {
    const safeLat = Number(params.lat);
    const safeLon = Number(params.lon);
    if (!Number.isFinite(safeLat) || safeLat < -90 || safeLat > 90) {
      setError("La latitud debe estar entre -90 y 90.");
      return;
    }
    if (!Number.isFinite(safeLon) || safeLon < -180 || safeLon > 180) {
      setError("La longitud debe estar entre -180 y 180.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const data = await recommendRotation({
        lat: safeLat,
        lon: safeLon,
        currentCrop: params.currentCrop,
        yearsSameCrop: Number(params.yearsSameCrop),
        polygon: params.polygon,
      });
      setResult(data);
      if (data.terrain_analysis?.area_ha) {
        setHectares(data.terrain_analysis.area_ha);
      }
      savePlotToHistory({
        label: params.label || `${safeLat.toFixed(2)}, ${safeLon.toFixed(2)}`,
        lat: safeLat,
        lon: safeLon,
        crop: params.currentCrop,
        cropName: data.current_crop?.name || params.currentCrop,
        years: String(params.yearsSameCrop),
        ha: data.terrain_analysis?.area_ha || Number(params.ha) || 25,
      });
    } catch (err) {
      setError(err.message || "No se pudo obtener la recomendación.");
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = (e) => {
    e.preventDefault();
    runAnalysis({
      lat,
      lon,
      currentCrop,
      yearsSameCrop,
      polygon,
      label: plotLabel,
      ha: hectares,
    });
  };

  const handleLoadEntry = (entry) => {
    setPolygon([]);
    setLat(entry.lat);
    setLon(entry.lon);
    setPlotLabel(entry.label || "");
    setCurrentCrop(entry.crop);
    setYearsSameCrop(entry.years);
    setHectares(entry.ha || 25);
    runAnalysis({
      lat: entry.lat,
      lon: entry.lon,
      currentCrop: entry.crop,
      yearsSameCrop: entry.years,
      polygon: [],
      label: entry.label,
      ha: entry.ha || 25,
    });
  };

  return (
    <TooltipProvider delayDuration={180}>
      <div className="min-h-screen bg-background">
        <header className="border-b bg-primary text-primary-foreground">
          <div className="container flex flex-wrap items-center justify-between gap-4 py-4">
            <div>
              <h1 className="flex items-center gap-2.5 text-xl font-bold tracking-tight sm:text-2xl">
                <Satellite className="h-6 w-6" />
                AgroNASA · Asistente de Rotación de Cultivos
              </h1>
              <p className="mt-0.5 text-sm text-primary-foreground/85">
                Clima & SMAP (NASA POWER) · Relieve SRTM · Suelo SoilGrids/SSURGO · NDVI MODIS · FAO GAEZ & Mercado
              </p>
            </div>
            <div className="no-print flex flex-wrap gap-1.5">
              <Badge variant="outline" className="border-white/25 bg-white/10 text-white">
                <Globe className="h-3.5 w-3.5" /> Web
              </Badge>
              <Badge variant="outline" className="border-white/25 bg-white/10 text-white">
                <MessageCircle className="h-3.5 w-3.5" /> WhatsApp
              </Badge>
              <Badge variant="outline" className="border-white/25 bg-white/10 text-white">
                <Smartphone className="h-3.5 w-3.5" /> App Móvil
              </Badge>
            </div>
          </div>
        </header>

        <main className="container space-y-6 py-6">
          <div className="no-print grid grid-cols-1 gap-6 lg:grid-cols-12">
            <div className="lg:col-span-7">
              <PlotMap
                lat={lat}
                lon={lon}
                polygon={polygon}
                onSelectCoords={(newLat, newLon, labelHint) => {
                  setLat(newLat);
                  setLon(newLon);
                  if (labelHint) setPlotLabel(labelHint);
                }}
                onChangePolygon={setPolygon}
                onEstimateAreaHa={(areaHa) => setHectares(areaHa)}
              />
            </div>

            <Card className="flex flex-col justify-between lg:col-span-5">
              <form onSubmit={handleAnalyze} className="flex h-full flex-col justify-between">
                <div>
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2">
                      <Sprout className="h-5 w-5 text-primary" />
                      Configuración del lote
                    </CardTitle>
                    <CardDescription>
                      Elegí tu cultivo actual, superficie del lote e historial de campañas.
                    </CardDescription>
                  </CardHeader>

                  <CardContent className="space-y-4">
                    <div className="grid grid-cols-3 gap-2">
                      <div className="space-y-1">
                        <label htmlFor="lat-input" className="text-xs font-medium text-muted-foreground">
                          Latitud
                        </label>
                        <Input
                          id="lat-input"
                          type="number"
                          step="0.0001"
                          min="-90"
                          max="90"
                          className="h-9 text-xs tabular-nums"
                          value={lat}
                          onChange={(e) => {
                            const v = parseFloat(e.target.value);
                            setLat(Number.isNaN(v) ? 0 : v);
                          }}
                        />
                      </div>
                      <div className="space-y-1">
                        <label htmlFor="lon-input" className="text-xs font-medium text-muted-foreground">
                          Longitud
                        </label>
                        <Input
                          id="lon-input"
                          type="number"
                          step="0.0001"
                          min="-180"
                          max="180"
                          className="h-9 text-xs tabular-nums"
                          value={lon}
                          onChange={(e) => {
                            const v = parseFloat(e.target.value);
                            setLon(Number.isNaN(v) ? 0 : v);
                          }}
                        />
                      </div>
                      <div className="space-y-1">
                        <label htmlFor="ha-input" className="text-xs font-medium text-muted-foreground">
                          Hectáreas
                        </label>
                        <Input
                          id="ha-input"
                          type="number"
                          step="0.5"
                          min="0.5"
                          max="100000"
                          className="h-9 text-xs tabular-nums"
                          value={hectares}
                          onChange={(e) => {
                            const v = parseFloat(e.target.value);
                            setHectares(Number.isNaN(v) ? 1 : v);
                          }}
                        />
                      </div>
                    </div>

                    <div className="space-y-1.5">
                      <span className="text-xs font-semibold text-foreground">
                        Cultivo actual / recién cosechado
                      </span>
                      <div className="grid grid-cols-2 gap-1.5" role="radiogroup" aria-label="Cultivo actual">
                        {crops.map((crop) => {
                          const selected = currentCrop === crop.id;
                          return (
                            <button
                              key={crop.id}
                              type="button"
                              role="radio"
                              aria-checked={selected}
                              onClick={() => setCurrentCrop(crop.id)}
                              className={`flex items-center gap-2 rounded-lg border px-2.5 py-2 text-left transition-colors ${
                                selected
                                  ? "border-primary bg-primary/10 text-foreground ring-1 ring-primary"
                                  : "bg-card text-foreground hover:bg-muted/50"
                              }`}
                            >
                              <Wheat
                                className={`h-4 w-4 shrink-0 ${
                                  selected ? "text-primary" : "text-muted-foreground"
                                }`}
                              />
                              <div className="min-w-0">
                                <div className="truncate text-xs font-semibold">{crop.name}</div>
                                <div className="truncate text-[10px] text-muted-foreground">
                                  {crop.category}
                                </div>
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    <div className="space-y-1.5">
                      <label htmlFor="years-select" className="text-xs font-semibold text-foreground">
                        Años seguidos con este cultivo
                      </label>
                      <Select value={yearsSameCrop} onValueChange={setYearsSameCrop}>
                        <SelectTrigger id="years-select" className="h-9">
                          <SelectValue placeholder="Seleccionar campañas" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="1">1 año (rotación normal)</SelectItem>
                          <SelectItem value="2">2 años seguidos</SelectItem>
                          <SelectItem value="3">3 o más años (alerta de monocultivo)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    {recentPlots.length > 0 && (
                      <div className="space-y-1.5">
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground">
                          <Clock className="h-3 w-3" /> Lotes recientes
                        </span>
                        <div className="flex flex-wrap gap-1.5">
                          {recentPlots.map((item, idx) => (
                            <Button
                              key={`${item.lat}-${item.lon}-${item.crop}-${idx}`}
                              type="button"
                              size="sm"
                              variant="outline"
                              className="h-6 rounded-full px-2.5 text-[11px]"
                              onClick={() => handleLoadEntry(item)}
                            >
                              {item.label} · {item.cropName}
                            </Button>
                          ))}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </div>

                <div className="space-y-3 p-5 pt-0">
                  {error && (
                    <Alert variant="destructive">
                      <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                      <AlertDescription>{error}</AlertDescription>
                    </Alert>
                  )}

                  <Button type="submit" size="lg" className="w-full" disabled={loading}>
                    {loading ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Consultando 5 pilares satelitales...
                      </>
                    ) : (
                      "Analizar 5 pilares y recomendar rotación"
                    )}
                  </Button>
                </div>
              </form>
            </Card>
          </div>

          {loading && <DashboardSkeleton />}

          {!loading && !result && (
            <Card className="no-print bg-card">
              <CardContent className="space-y-5 p-6">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                  <div className="rounded-lg border bg-muted/25 p-4">
                    <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                      <MapPin className="h-4 w-4 text-primary" />
                      Ubicá tu parcela
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                      Activá la vista satelital para delimitar el polígono del lote o buscá tu localidad con sugerencias en vivo.
                    </p>
                  </div>
                  <div className="rounded-lg border bg-muted/25 p-4">
                    <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                      <Database className="h-4 w-4 text-primary" />
                      Cruce de 5 pilares + caché
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                      Validamos tierra firme vía SRTM y cruzamos NASA POWER/SMAP, SoilGrids/SSURGO y caché SQLite local.
                    </p>
                  </div>
                  <div className="rounded-lg border bg-muted/25 p-4">
                    <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                      <Sparkles className="h-4 w-4 text-primary" />
                      Decisión clara y exportable
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                      Obtendrás semáforos del lote, calendario 12 meses, comparativa radar, total para tus hectáreas y PDF/WhatsApp.
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/20 px-4 py-3">
                  <span className="text-xs font-semibold text-foreground">
                    ¿Querés probarlo en 1 clic? Elegí un lote de muestra:
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {QUICK_EXAMPLES.map((ex) => (
                      <Button
                        key={ex.label}
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={() => handleLoadEntry({ ...ex, cropName: ex.crop })}
                      >
                        {ex.label}
                      </Button>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {!loading && result && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border bg-card px-4 py-2.5 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="inline-flex items-center gap-1.5 font-semibold text-foreground">
                    <CheckCircle2 className="h-4 w-4 text-emerald-700" />
                    Parcela ({result.location.lat.toFixed(4)}, {result.location.lon.toFixed(4)}) ·{" "}
                    <span className="tabular-nums">{hectares} ha</span>
                  </span>
                  {result.data_provenance && (
                    <Badge variant={result.data_provenance.cache_hits > 0 ? "success" : "secondary"}>
                      <Database className="h-3 w-3" />
                      {result.data_provenance.cache_hits > 0
                        ? `Caché SQLite (${result.data_provenance.cache_hits}/3)`
                        : "Consulta en vivo"}
                    </Badge>
                  )}
                </div>
                <div className="flex flex-wrap gap-1.5 text-muted-foreground">
                  <Badge variant="outline">Clima: {formatSourceTag(result.climate_analysis.source)}</Badge>
                  <Badge variant="outline">Relieve: {formatSourceTag(result.terrain_analysis.source)}</Badge>
                  <Badge variant="outline">Suelo: {formatSourceTag(result.soil_profile.source)}</Badge>
                </div>
              </div>

              <VerdictBanner
                result={result}
                hectares={hectares}
                whatsappShareText={result.channel_payload?.whatsapp_message}
              />

              <ClimateDashboard
                climate={result.climate_analysis}
                terrain={result.terrain_analysis}
                soil={result.soil_profile}
                vegetation={result.vegetation_health}
                scenarios={result.scenarios}
              />

              <RotationScenarios
                scenarios={result.scenarios}
                currentCrop={result.current_crop}
                anomalies={result.climate_analysis.anomalies}
                hectares={hectares}
                whatsappShareText={result.channel_payload?.whatsapp_message}
              />

              <div className="no-print">
                <ChannelPreview
                  key={`${result.location.lat}-${result.location.lon}-${result.current_crop.id}`}
                  recommendation={result}
                  lat={result.location.lat}
                  lon={result.location.lon}
                  currentCropId={result.current_crop.id}
                />
              </div>
            </>
          )}
        </main>
      </div>
    </TooltipProvider>
  );
}
