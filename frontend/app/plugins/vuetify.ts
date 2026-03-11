import { createVuetify } from 'vuetify'

export default defineNuxtPlugin((nuxtApp) => {
  const vuetify = createVuetify({
    theme: {
      defaultTheme: 'vuecutter',
      themes: {
        vuecutter: {
          dark: false,
          colors: {
            background: '#eef3f8',
            surface: '#ffffff',
            primary: '#1f4a7c',
            secondary: '#3b6f8f',
            accent: '#d97706',
          },
        },
      },
    },
  })

  nuxtApp.vueApp.use(vuetify)
})
