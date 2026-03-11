import vuetify from 'vite-plugin-vuetify'

export default defineNuxtConfig({
  compatibilityDate: '2026-03-11',
  devtools: { enabled: true },
  ssr: false,
  css: [
    '@mdi/font/css/materialdesignicons.css',
    'vuetify/styles',
    '~/app/assets/main.scss',
  ],
  build: {
    transpile: ['vuetify'],
  },
  vite: {
    ssr: {
      noExternal: ['vuetify'],
    },
    plugins: [vuetify({ autoImport: true })],
    define: {
      'process.env.DEBUG': false,
    },
  },
  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || 'http://localhost:5200',
    },
  },
})
