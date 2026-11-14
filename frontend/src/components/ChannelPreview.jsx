import React, { useState } from "react";
import { Check, Code2, Copy, MessageCircle, RotateCcw, Send, Smartphone } from "lucide-react";
import { sendWhatsAppSimulation } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function ChannelPreview({ recommendation, lat, lon, currentCropId }) {
  const [waInput, setWaInput] = useState(
    `rotacion ${currentCropId} ${lat.toFixed(4)}, ${lon.toFixed(4)}`
  );
  const [chatHistory, setChatHistory] = useState(() => [
    { from: "user", text: `rotacion ${currentCropId} ${lat.toFixed(4)}, ${lon.toFixed(4)}` },
    {
      from: "bot",
      text: recommendation?.channel_payload?.whatsapp_message || "",
    },
  ]);
  const [sendingWa, setSendingWa] = useState(false);
  const [copiedJson, setCopiedJson] = useState(false);

  const mobile = recommendation?.channel_payload?.mobile_compact;

  const compactApiSummary = {
    location: recommendation?.location,
    data_provenance: recommendation?.data_provenance,
    storm_metrics: {
      extreme_rain_days_gt40mm: recommendation?.climate_analysis?.anomalies?.extreme_rain_days_gt40mm,
      max_daily_rain_mm: recommendation?.climate_analysis?.anomalies?.max_daily_rain_mm,
    },
    vegetation_health: {
      estimated_ndvi: recommendation?.vegetation_health?.estimated_ndvi,
      soil_exhaustion_risk: recommendation?.vegetation_health?.soil_exhaustion_risk,
      cdl_history: recommendation?.vegetation_health?.cdl_history,
    },
    top_scenarios: (recommendation?.scenarios || []).map((s) => ({
      rank: s.scenario_rank,
      crop: s.crop_name,
      score: s.suitability_score,
      sowing_window: s.sowing_window,
      margin_usd_ha: s.economics.estimated_margin_usd_ha,
    })),
  };

  const sendMessageToWebhook = async (textToSend) => {
    const trimmed = textToSend.trim();
    if (!trimmed) return;
    setSendingWa(true);
    setChatHistory((prev) => [...prev, { from: "user", text: trimmed }]);
    try {
      const res = await sendWhatsAppSimulation({
        fromNumber: "whatsapp:+549351000001",
        body: trimmed,
      });
      setChatHistory((prev) => [...prev, { from: "bot", text: res.reply_text }]);
    } catch (err) {
      setChatHistory((prev) => [...prev, { from: "bot", text: `Error: ${err.message}` }]);
    } finally {
      setSendingWa(false);
    }
  };

  const handleTestWebhook = (e) => {
    e.preventDefault();
    sendMessageToWebhook(waInput);
  };

  const handleCopyJson = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(compactApiSummary, null, 2));
      setCopiedJson(true);
      setTimeout(() => setCopiedJson(false), 2000);
    } catch {
      setCopiedJson(false);
    }
  };

  return (
    <Card>
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center gap-2">
          <Smartphone className="h-5 w-5 text-primary" />
          Canales de consulta: Web, WhatsApp (2 pasos) y App Móvil
        </CardTitle>
        <CardDescription>
          El mismo motor REST abastece al dashboard web, al bot conversacional de WhatsApp (Twilio TwiML / Meta JSON) y a apps móviles offline-first.
        </CardDescription>
      </CardHeader>

      <CardContent>
        <Tabs defaultValue="whatsapp" className="w-full">
          <TabsList className="flex-wrap">
            <TabsTrigger value="whatsapp">
              <MessageCircle className="h-4 w-4" />
              Canal WhatsApp (2 pasos / Twilio)
            </TabsTrigger>
            <TabsTrigger value="mobile">
              <Smartphone className="h-4 w-4" />
              Canal App Móvil (Payload compacto)
            </TabsTrigger>
            <TabsTrigger value="json">
              <Code2 className="h-4 w-4" />
              API REST / Trazabilidad
            </TabsTrigger>
          </TabsList>

          <TabsContent value="whatsapp" className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-medium text-muted-foreground">Simular flujo en 2 pasos:</span>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={sendingWa}
                onClick={() => sendMessageToWebhook(`${lat.toFixed(4)}, ${lon.toFixed(4)}`)}
              >
                Paso 1: Enviar solo coordenadas
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={sendingWa}
                onClick={() => sendMessageToWebhook("1 3 años")}
              >
                Paso 2: Responder &quot;1 3 años&quot;
              </Button>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                disabled={sendingWa}
                onClick={() => {
                  setChatHistory([]);
                  sendMessageToWebhook("reset");
                }}
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Reiniciar
              </Button>
            </div>

            <form onSubmit={handleTestWebhook} className="flex flex-wrap gap-2">
              <Input
                type="text"
                className="min-w-[240px] flex-1"
                value={waInput}
                onChange={(e) => setWaInput(e.target.value)}
                placeholder="Ej: -31.48, -63.55 o '1 3 años'"
                aria-label="Mensaje de prueba para webhook WhatsApp"
              />
              <Button type="submit" variant="secondary" disabled={sendingWa}>
                <Send className="h-4 w-4" />
                {sendingWa ? "Consultando..." : "Enviar mensaje"}
              </Button>
            </form>

            <div className="max-w-xl overflow-hidden rounded-2xl border border-stone-300 bg-[#efeae2]">
              <div className="flex items-center justify-between bg-[#075e54] px-4 py-2.5 text-sm font-semibold text-white">
                <span>AgroNASA Bot · WhatsApp</span>
                <span className="text-[11px] font-normal text-white/80">Sesión SQLite activa</span>
              </div>
              <div className="flex max-h-96 flex-col gap-3 overflow-y-auto p-4">
                {chatHistory.map((item, idx) => (
                  <div
                    key={idx}
                    className={
                      item.from === "user"
                        ? "self-end rounded-lg bg-[#dcf8c6] px-3 py-2 text-xs text-stone-900 shadow-sm"
                        : "max-w-[95%] self-start whitespace-pre-wrap rounded-lg bg-white px-3.5 py-2.5 text-xs leading-relaxed text-stone-800 shadow-sm"
                    }
                  >
                    {item.text}
                  </div>
                ))}
              </div>
            </div>
          </TabsContent>

          <TabsContent value="mobile">
            {mobile && (
              <div className="max-w-sm rounded-[28px] bg-stone-900 p-3 shadow-lg">
                <div className="space-y-2.5 rounded-[20px] bg-background p-4">
                  <div className="text-sm font-bold text-foreground">
                    AgroNASA Móvil · Tras {mobile.current_crop_name}
                  </div>
                  <div className="flex flex-wrap gap-1">
                    <Badge variant="outline" className="text-[11px]">
                      {mobile.summary_badges.climate_zone}
                    </Badge>
                    <Badge variant="outline" className="text-[11px] tabular-nums">
                      SMAP {mobile.summary_badges.smap_wetness_pct}%
                    </Badge>
                    <Badge variant="outline" className="text-[11px] tabular-nums">
                      NDVI {mobile.summary_badges.estimated_ndvi}
                    </Badge>
                    <Badge variant="outline" className="text-[11px] tabular-nums">
                      pH {mobile.summary_badges.soil_ph}
                    </Badge>
                  </div>

                  {mobile.cards.map((card) => (
                    <div key={card.crop_id} className="space-y-1 rounded-lg border bg-card p-3">
                      <div className="flex items-center justify-between text-sm font-bold">
                        <span>
                          #{card.rank} {card.crop_name}
                        </span>
                        <span className="text-primary tabular-nums">{Math.round(card.score)} pts</span>
                      </div>
                      <p className="text-xs font-semibold text-emerald-800 tabular-nums">
                        Siembra: {card.sowing_window} · Margen USD {Math.round(card.estimated_margin_usd_ha)}/ha (
                        {card.price_trend_pct >= 0 ? "+" : ""}
                        {card.price_trend_pct}%)
                      </p>
                      <p className="text-xs text-muted-foreground">
                        <strong className="text-foreground">Por qué:</strong> {card.why}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        <strong className="text-foreground">Suelo:</strong> {card.soil_benefit}
                      </p>
                      <p className="text-xs text-primary">
                        <strong>Secuencia:</strong> {card.sequence_summary}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </TabsContent>

          <TabsContent value="json" className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs text-muted-foreground">
                Endpoints: <code className="rounded bg-muted px-1 py-0.5">/api/recommend-rotation</code> ·{" "}
                <code className="rounded bg-muted px-1 py-0.5">/api/channels/whatsapp/twilio</code> (TwiML XML)
              </p>
              <Button type="button" size="sm" variant="outline" onClick={handleCopyJson}>
                {copiedJson ? <Check className="h-3.5 w-3.5 text-emerald-700" /> : <Copy className="h-3.5 w-3.5" />}
                {copiedJson ? "Copiado" : "Copiar JSON"}
              </Button>
            </div>
            <pre className="max-h-72 overflow-auto rounded-lg border bg-muted/40 p-3.5 text-xs text-foreground tabular-nums">
              {JSON.stringify(compactApiSummary, null, 2)}
            </pre>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
