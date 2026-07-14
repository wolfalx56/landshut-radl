import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    svelte(),
    VitePWA({
      selfDestroying: true,
      injectRegister: null,
      registerType: 'autoUpdate',
      workbox: {
        navigateFallbackDenylist: [/^\/akito/, /^\/radai/],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/tiles\.openfreemap\.org\/.*/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'map-tiles',
              expiration: { maxEntries: 5000, maxAgeSeconds: 60 * 60 * 24 * 30 },
            },
          },
          {
            urlPattern: /^https:\/\/routing\.openstreetmap\.de\/.*/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'routing',
              expiration: { maxEntries: 100, maxAgeSeconds: 60 * 60 * 24 * 7 },
            },
          },
          {
            urlPattern: /^https:\/\/overpass-api\.de\/.*/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'overpass',
              expiration: { maxEntries: 50, maxAgeSeconds: 60 * 60 * 24 },
            },
          },
          {
            urlPattern: /^https:\/\/api\.open-meteo\.com\/.*/,
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'weather',
              expiration: { maxEntries: 10, maxAgeSeconds: 3600 },
            },
          },
        ],
      },
      manifest: {
        name: 'Landshut Radl',
        short_name: 'Radl',
        description: 'Radtouren rund um Landshut',
        theme_color: '#2d6a4f',
        background_color: '#ffffff',
        display: 'standalone',
        orientation: 'portrait',
        start_url: '/',
        icons: [
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
    }),
  ],
})
