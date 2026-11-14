const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

async function requestJson(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail || "Error al consultar la API");
  }
  return response.json();
}

export function fetchCrops() {
  return requestJson("/api/crops");
}

export function recommendRotation({
  lat,
  lon,
  currentCrop,
  yearsSameCrop = 1,
  polygon = [],
}) {
  const payload = {
    lat,
    lon,
    current_crop: currentCrop,
    years_same_crop: yearsSameCrop,
    channel: "web",
  };
  if (Array.isArray(polygon) && polygon.length >= 3) {
    payload.polygon = polygon;
  }
  return requestJson("/api/recommend-rotation", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function sendWhatsAppSimulation({ body, latitude, longitude }) {
  return requestJson("/api/channels/whatsapp/webhook", {
    method: "POST",
    body: JSON.stringify({
      from_number: "whatsapp:+549351000000",
      body,
      latitude,
      longitude,
    }),
  });
}
