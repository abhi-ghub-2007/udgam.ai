import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';
import path from 'node:path';

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['assets/logo.svg'],
      manifest: {
        name: 'UDGAM.ai',
        short_name: 'UDGAM',
        description: 'Farmers and buyers, directly connected.',
        theme_color: '#006e1c',
        background_color: '#fcf9f2',
        display: 'standalone',
        start_url: '/',
        icons: [{ src: 'assets/logo.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' }],
      },
      workbox: {
        // App shell + static assets only. API responses are NEVER precached or
        // runtime-cached: they are per-user, RLS-scoped and often sensitive, and
        // a shared browser cache is the wrong place for them (master prompt 35).
        globPatterns: ['**/*.{js,css,html,svg,woff2}'],
        navigateFallback: 'index.html',
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [],
      },
    }),
  ],
  resolve: {
    alias: { '@': path.resolve(__dirname, 'src') },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        // Keep the heavy, lazily-used libraries in their own chunks so they are
        // never part of the initial shell. Verified against the real bundle.
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-query': ['@tanstack/react-query'],
          'vendor-supabase': ['@supabase/supabase-js'],
          'vendor-i18n': ['i18next', 'react-i18next'],
        },
      },
    },
  },
  server: { port: 3000, host: '127.0.0.1' },
});
