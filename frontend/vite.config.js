import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon.svg", "icon-192.png", "icon-512.png"],
      manifest: {
        name: "AgroNASA · Rotación Inteligente de Cultivos",
        short_name: "AgroNASA",
        description:
          "Asistente agronómico offline-first con NASA POWER, SMAP, SRTM, SoilGrids, USDA CDL y FAO GAEZ.",
        theme_color: "#1e4d36",
        background_color: "#f7f9f5",
        display: "standalone",
        lang: "es",
        icons: [
          {
            src: "icon-192.png",
            sizes: "192x192",
            type: "image/png",
          },
          {
            src: "icon-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any maskable",
          },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,ico,png,svg,woff2}"],
        runtimeCaching: [
          {
            urlPattern: /\/api\/(crops|health)/,
            handler: "StaleWhileRevalidate",
            options: {
              cacheName: "agronasa-catalog-cache",
              expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 7 },
            },
          },
          {
            urlPattern: /\/api\/recommend-rotation/,
            handler: "NetworkFirst",
            options: {
              cacheName: "agronasa-recommendations-cache",
              networkTimeoutSeconds: 10,
              expiration: { maxEntries: 30, maxAgeSeconds: 60 * 60 * 24 * 7 },
            },
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom"],
          "vendor-leaflet": ["leaflet", "react-leaflet"],
          "vendor-recharts": ["recharts"],
          "vendor-radix": [
            "@radix-ui/react-select",
            "@radix-ui/react-separator",
            "@radix-ui/react-slot",
            "@radix-ui/react-tabs",
            "@radix-ui/react-tooltip",
          ],
        },
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_BACKEND_PROXY || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
