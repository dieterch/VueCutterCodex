import vuetify from 'vite-plugin-vuetify'

export default defineNuxtConfig({
  compatibilityDate: '2026-03-11',
  devtools: { enabled: true },
  ssr: false,
  srcDir: 'app/',
  css: [
    '@mdi/font/css/materialdesignicons.css',
    'vuetify/styles',
    '~/assets/main.scss',
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
    apiProxyBase: process.env.API_PROXY_BASE || 'http://backend:5200',
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || '',
    },
  },
})
