import React, { useEffect, useState } from "react";
import {
  CircleMarker,
  MapContainer,
  Marker,
  Polygon,
  Popup,
  TileLayer,
  useMap,
  useMapEvents,
} from "react-leaflet";
import L from "leaflet";
import markerIcon2x from "leaflet/dist/images/marker-icon-2x.png";
import markerIcon from "leaflet/dist/images/marker-icon.png";
import markerShadow from "leaflet/dist/images/marker-shadow.png";
import {
  Compass,
  Eye,
  Layers,
  MapPin,
  Pentagon,
  Search,
  Trash2,
  Undo2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});

const NASA_GIBS_NDVI_URL =
  "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_NDVI_8Day/default/2025-10-16/GoogleMapsCompatible_Level9/{z}/{y}/{x}.png";

const ESRI_SATELLITE_URL =
  "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}";

const PRESET_REGIONS = [
  { label: "Córdoba Rural, Arg", lat: -31.48, lon: -63.55 },
  { label: "Boyacá Rural, Col", lat: 5.58, lon: -73.3 },
  { label: "Bajío Rural, Méx", lat: 20.62, lon: -101.28 },
  { label: "Iowa, EE.UU. (SSURGO)", lat: 41.9, lon: -93.6 },
];

const EARTH_RADIUS_M = 6378137.0;

function estimatePolygonHa(pts) {
  if (!pts || pts.length < 3) return null;
  const avgLat = pts.reduce((a, p) => a + p.lat, 0) / pts.length;
  const avgLon = pts.reduce((a, p) => a + p.lon, 0) / pts.length;
  const cosLat = Math.max(0.1, Math.cos((avgLat * Math.PI) / 180));
  const mPerDegLat = (Math.PI / 180) * EARTH_RADIUS_M;
  const mPerDegLon = mPerDegLat * cosLat;

  const proj = pts.map((p) => [
    (p.lon - avgLon) * mPerDegLon,
    (p.lat - avgLat) * mPerDegLat,
  ]);
  let twiceArea = 0;
  for (let i = 0; i < proj.length; i += 1) {
    const [x1, y1] = proj[i];
    const [x2, y2] = proj[(i + 1) % proj.length];
    twiceArea += x1 * y2 - x2 * y1;
  }
  return Math.max(0.1, Number((Math.abs(twiceArea) / 2 / 10000).toFixed(2)));
}

function MapClickHandler({ drawingMode, onSelectPoint, onAddVertex }) {
  useMapEvents({
    click(e) {
      const lat = Number(e.latlng.lat.toFixed(5));
      const lon = Number(e.latlng.lng.toFixed(5));
      if (drawingMode) {
        onAddVertex({ lat, lon });
      } else {
        onSelectPoint(lat, lon);
      }
    },
  });
  return null;
}

function RecenterMap({ lat, lon }) {
  const map = useMap();
  useEffect(() => {
    if (Number.isFinite(lat) && Number.isFinite(lon)) {
      map.setView([lat, lon], map.getZoom());
    }
  }, [lat, lon, map]);
  return null;
}

export default function PlotMap({
  lat,
  lon,
  polygon,
  onSelectCoords,
  onChangePolygon,
  onEstimateAreaHa,
}) {
  const [drawingMode, setDrawingMode] = useState(false);
  const [showNdvi, setShowNdvi] = useState(false);
  const [ndviOpacity, setNdviOpacity] = useState(0.68);
  const [satelliteBase, setSatelliteBase] = useState(false);
  const [placeQuery, setPlaceQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [searchingPlace, setSearchingPlace] = useState(false);
  const [searchError, setSearchError] = useState("");

  useEffect(() => {
    const q = placeQuery.trim();
    if (q.length < 3) {
      setSuggestions([]);
      return undefined;
    }

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(
          `https://nominatim.openstreetmap.org/search?format=json&limit=5&q=${encodeURIComponent(q)}`,
          { headers: { Accept: "application/json" }, signal: controller.signal }
        );
        if (!res.ok) return;
        const hits = await res.json();
        if (Array.isArray(hits)) {
          setSuggestions(hits);
        }
      } catch {
        // Ignore abort / offline errors during typing autocomplete
      }
    }, 350);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [placeQuery]);

  const applyHit = (hit) => {
    onChangePolygon([]);
    onSelectCoords(
      Number(parseFloat(hit.lat).toFixed(5)),
      Number(parseFloat(hit.lon).toFixed(5)),
      hit.display_name?.split(",").slice(0, 2).join(",")
    );
    setSuggestions([]);
    setSearchError("");
  };

  const handleUseGps = () => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        onChangePolygon([]);
        onSelectCoords(
          Number(pos.coords.latitude.toFixed(5)),
          Number(pos.coords.longitude.toFixed(5)),
          "Mi ubicación GPS"
        );
      },
      () => {}
    );
  };

  const handleSearchPlace = async (e) => {
    e.preventDefault();
    const q = placeQuery.trim();
    if (!q) return;
    if (suggestions.length > 0) {
      applyHit(suggestions[0]);
      return;
    }
    setSearchingPlace(true);
    setSearchError("");
    try {
      const res = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&limit=5&q=${encodeURIComponent(q)}`,
        { headers: { Accept: "application/json" } }
      );
      if (!res.ok) throw new Error("No se pudo buscar la localidad.");
      const hits = await res.json();
      if (!Array.isArray(hits) || hits.length === 0) {
        setSearchError("No se encontró esa localidad. Probá agregando país o provincia.");
        return;
      }
      applyHit(hits[0]);
    } catch {
      setSearchError("Buscador no disponible sin conexión; hacé clic directo en el mapa.");
    } finally {
      setSearchingPlace(false);
    }
  };

  const syncPolygonMetrics = (updated) => {
    onChangePolygon(updated);
    if (updated.length > 0) {
      const avgLat = updated.reduce((acc, p) => acc + p.lat, 0) / updated.length;
      const avgLon = updated.reduce((acc, p) => acc + p.lon, 0) / updated.length;
      onSelectCoords(Number(avgLat.toFixed(5)), Number(avgLon.toFixed(5)));
    }
    if (onEstimateAreaHa) {
      const est = estimatePolygonHa(updated);
      if (est !== null) onEstimateAreaHa(est);
    }
  };

  const handleAddVertex = (pt) => {
    syncPolygonMetrics([...polygon, pt]);
  };

  const handleUndoVertex = () => {
    if (polygon.length === 0) return;
    syncPolygonMetrics(polygon.slice(0, -1));
  };

  const handleClearPolygon = () => {
    onChangePolygon([]);
    setDrawingMode(false);
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2 text-foreground">
              <MapPin className="h-5 w-5 text-primary" />
              Ubicación de la parcela
            </CardTitle>
            <CardDescription>
              {drawingMode
                ? "Modo dibujo activo: marcá los vértices del lote (mínimo 3) para medir hectáreas y pendiente zonal."
                : "Hacé clic en el mapa, activá vista satelital, buscá tu municipio o cargá la capa NDVI."}
            </CardDescription>
          </div>

          <div className="flex flex-wrap gap-1.5">
            <Button
              type="button"
              size="sm"
              variant={satelliteBase ? "default" : "outline"}
              onClick={() => setSatelliteBase((v) => !v)}
            >
              <Layers className="h-3.5 w-3.5" />
              {satelliteBase ? "Vista Satélite" : "Satélite"}
            </Button>

            <Button
              type="button"
              size="sm"
              variant={showNdvi ? "default" : "outline"}
              onClick={() => setShowNdvi((v) => !v)}
            >
              <Eye className="h-3.5 w-3.5" />
              {showNdvi ? "Ocultar NDVI" : "NDVI NASA"}
            </Button>

            <Button
              type="button"
              size="sm"
              variant={drawingMode ? "default" : "outline"}
              onClick={() => setDrawingMode((v) => !v)}
            >
              <Pentagon className="h-3.5 w-3.5" />
              {drawingMode ? "Terminar lote" : "Dibujar lote"}
            </Button>

            {drawingMode && polygon.length > 0 && (
              <Button type="button" size="sm" variant="outline" onClick={handleUndoVertex}>
                <Undo2 className="h-3.5 w-3.5" />
                Deshacer
              </Button>
            )}

            {polygon.length > 0 && (
              <Button type="button" size="sm" variant="outline" onClick={handleClearPolygon}>
                <Trash2 className="h-3.5 w-3.5" />
                Limpiar ({polygon.length})
              </Button>
            )}

            <Button type="button" size="sm" variant="outline" onClick={handleUseGps}>
              <Compass className="h-3.5 w-3.5" />
              GPS
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        <div className="relative">
          <form onSubmit={handleSearchPlace} className="flex gap-2">
            <Input
              type="text"
              value={placeQuery}
              onChange={(e) => setPlaceQuery(e.target.value)}
              placeholder="Buscar municipio o zona (ej. Pergamino, Tunja, Celaya)..."
              aria-label="Buscar localidad en el mapa"
            />
            <Button type="submit" variant="secondary" disabled={searchingPlace}>
              <Search className="h-4 w-4" />
              {searchingPlace ? "Buscando..." : "Ir"}
            </Button>
          </form>

          {suggestions.length > 0 && (
            <div className="absolute left-0 right-0 top-full z-[500] mt-1 overflow-hidden rounded-lg border bg-popover shadow-md">
              {suggestions.map((hit) => (
                <button
                  key={`${hit.place_id}`}
                  type="button"
                  onClick={() => applyHit(hit)}
                  className="flex w-full items-start gap-2 border-b px-3 py-2 text-left text-xs text-popover-foreground last:border-b-0 hover:bg-muted/60"
                >
                  <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                  <span className="line-clamp-1">{hit.display_name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        {searchError && <p className="text-xs text-destructive">{searchError}</p>}

        <div className="flex flex-wrap items-center gap-1.5">
          <span className="mr-1 text-xs font-medium text-muted-foreground">Zonas demo:</span>
          {PRESET_REGIONS.map((region) => (
            <Button
              key={region.label}
              type="button"
              size="sm"
              variant="secondary"
              className="h-7 rounded-full px-3 text-xs font-medium"
              onClick={() => {
                onChangePolygon([]);
                onSelectCoords(region.lat, region.lon, region.label);
              }}
            >
              {region.label}
            </Button>
          ))}
        </div>

        <div className="h-[360px] overflow-hidden rounded-lg border">
          <MapContainer center={[lat, lon]} zoom={9} className="h-full w-full">
            {satelliteBase ? (
              <TileLayer
                attribution="Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics"
                url={ESRI_SATELLITE_URL}
              />
            ) : (
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
            )}

            {showNdvi && (
              <TileLayer
                attribution="NASA GIBS MODIS Terra NDVI"
                url={NASA_GIBS_NDVI_URL}
                opacity={ndviOpacity}
                maxNativeZoom={9}
                maxZoom={18}
              />
            )}

            <MapClickHandler
              drawingMode={drawingMode}
              onSelectPoint={(newLat, newLon) => onSelectCoords(newLat, newLon)}
              onAddVertex={handleAddVertex}
            />
            <RecenterMap lat={lat} lon={lon} />

            {polygon.length >= 3 && (
              <Polygon
                positions={polygon.map((p) => [p.lat, p.lon])}
                pathOptions={{ color: "#1e4d36", fillColor: "#40916c", fillOpacity: 0.35 }}
              />
            )}

            {polygon.map((p, idx) => (
              <CircleMarker
                key={`${p.lat}-${p.lon}-${idx}`}
                center={[p.lat, p.lon]}
                radius={5}
                pathOptions={{ color: "#1b4332", fillColor: "#ffffff", fillOpacity: 1 }}
              />
            ))}

            {polygon.length < 3 && (
              <Marker position={[lat, lon]}>
                <Popup>
                  Parcela seleccionada
                  <br />
                  Lat: {lat.toFixed(4)} | Lon: {lon.toFixed(4)}
                </Popup>
              </Marker>
            )}
          </MapContainer>
        </div>

        {showNdvi && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/35 px-3 py-2 text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-foreground">MODIS NDVI:</span>
              <span>Bajo</span>
              <span className="inline-block h-2.5 w-24 rounded-full bg-gradient-to-r from-amber-700 via-yellow-400 to-emerald-700" />
              <span>Vigoroso</span>
            </div>
            <label className="flex items-center gap-2">
              <span className="font-medium text-foreground">Opacidad ({Math.round(ndviOpacity * 100)}%)</span>
              <input
                type="range"
                min="0.3"
                max="0.95"
                step="0.05"
                value={ndviOpacity}
                onChange={(e) => setNdviOpacity(parseFloat(e.target.value))}
                className="h-1.5 w-24 accent-primary"
              />
            </label>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
