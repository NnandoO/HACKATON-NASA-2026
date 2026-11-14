# AgroNASA · Sistema Base Multicanal de Rotación de Cultivos

Modelo base para recomendar rotaciones de cultivos a agricultores combinando:
- **Reglas agronómicas FAO simuladas** (`data/fao_crops_rules.json`, 8 cultivos base).
- **NASA POWER API** (análisis histórico y anomalías recientes de lluvia y temperatura con `pandas`).
- **NASA SRTM 90m** vía OpenTopoData (cálculo de elevación y pendiente del lote en `%` y grados).
- **Motor de Decisión (`rotation_engine.py`)** que genera **3 escenarios comparativos** con explicaciones claras.
- **Arquitectura Base Multicanal** lista para servir **Web (React)**, **WhatsApp (Webhook)** y **App Móvil (API compacta)**.

## Estructura del Proyecto

```text
agro-rotacion-nasa/
├── data/
│   └── fao_crops_rules.json          # Base de cultivos FAO (límites de lluvia, temp, pendiente y beneficio al suelo)
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py                   # FastAPI app + CORS
│       ├── schemas.py                # Modelos Pydantic compartidos
│       ├── services/
│       │   ├── crop_catalog.py       # Carga y resolución de cultivos
│       │   ├── nasa_power.py         # Cliente NASA POWER + anomalías con pandas
│       │   ├── srtm_elevation.py     # Cliente SRTM + cálculo de pendiente
│       │   └── rotation_engine.py    # Motor de decisión de 3 escenarios
│       ├── channels/
│       │   ├── base.py               # Orquestador agnóstico al canal
│       │   ├── web_presenter.py      # Respuesta enriquecida para Web
│       │   ├── whatsapp_adapter.py   # Parser de texto/ubicación y formateador WhatsApp
│       │   └── mobile_presenter.py   # Payload compacto para App Móvil (3G/4G)
│       └── api/routes.py             # Endpoints REST (/api/recommend-rotation y canales)
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/components/
│       ├── PlotMap.jsx               # Mapa interactivo Leaflet (clic para capturar lat/lon)
│       ├── ClimateDashboard.jsx      # Gráficas Recharts de temperatura y lluvia NASA
│       ├── RotationScenarios.jsx     # 3 escenarios comparativos ("Por qué" + "Beneficios al suelo")
│       └── ChannelPreview.jsx        # Simulador en vivo de WhatsApp y vista App Móvil
└── docker-compose.yml
```

## Endpoints Principales

- `GET /api/crops`: Lista los 8 cultivos base y sus reglas FAO.
- `POST /api/recommend-rotation`: Recibe `{"lat": -31.4201, "lon": -63.6167, "current_crop": "maiz"}` y devuelve análisis NASA POWER, pendiente SRTM y 3 escenarios de rotación.
- `POST /api/channels/whatsapp/webhook`: Recibe mensajes tipo `"rotacion maiz -31.42, -63.61"` o pines de ubicación y responde texto formateado para WhatsApp.
- `POST /api/channels/mobile/recommend`: Devuelve tarjetas compactas optimizadas para aplicación móvil.

## Ejecución Rápida con Docker

```bash
docker-compose up --build
```

- Frontend Web: `http://localhost:5173`
- Backend Swagger API: `http://localhost:8000/docs`
