/**
 * plugins/vuetify.js
 *
 * Framework documentation: https://vuetifyjs.com`
 */

// Styles
import '@mdi/font/css/materialdesignicons.css'
import 'vuetify/styles'

// Composables
import { createVuetify } from 'vuetify'

// https://vuetifyjs.com/en/introduction/why-vuetify/#feature-guides
/* export default createVuetify({
  theme: {
    defaultTheme: 'light'
  }
}) */


const DarkTheme = {
  dark: true,
  colors: {
    background: '#000000',
    surface: '#FFFFFF',
    primary: '#1867C0',
    secondary: '#48A9A6',
    error: '#B00020',
    info: '#2196F3',
    success: '#4CAF50',
    warning: '#FB8C00',
    tertiary: '#AAAAAA',
    // Application specific colors
    'toolsbackground': '#424242',
    'dialogbackground': '#424242',
    'primary-button': '#ffa726',
    'secondary-button': '#ff5722',
    'tertiary-button': '#222222',
    'danger-button': '#91a7ff',
  },
  variables: {
    'border-color': '#000000',
    'border-opacity': 0.12,
    'high-emphasis-opacity': 0.87,
    'medium-emphasis-opacity': 0.60,
    'disabled-opacity': 0.38,
    'idle-opacity': 0.04,
    'hover-opacity': 0.04,
    'focus-opacity': 0.12,
    'selected-opacity': 0.08,
    'activated-opacity': 0.12,
    'pressed-opacity': 0.12,
    'dragged-opacity': 0.08,
    'theme-kbd': '#212529',
    'theme-on-kbd': '#FFFFFF',
    'theme-code': '#F5F5F5',
    'theme-on-code': '#000000',
  }
}

const LightTheme = {
  dark: false,
  colors: {
    background: '#191818E0',
    surface: '#FFFFFF',
    primary: '#1867C0',
    secondary: '#48A9A6',
    error: '#B00020',
    info: '#2196F3',
    success: '#4CAF50',
    warning: '#FB8C00',
    tertiary: '#AAAAAA',
    // Application specific colors
    'toolsbackground': '#EEEEEE',
    'dialogbackground': '#EEEEEE',
    'primary-button': '#1867C0',
    'secondary-button': '#48A9A6',
    'tertiary-button': '#C0C0C0',
    'danger-button': '#B00020',
  },
  variables: {
    'border-color': '#000000',
    'border-opacity': 0.12,
    'high-emphasis-opacity': 0.87,
    'medium-emphasis-opacity': 0.60,
    'disabled-opacity': 0.38,
    'idle-opacity': 0.04,
    'hover-opacity': 0.04,
    'focus-opacity': 0.12,
    'selected-opacity': 0.08,
    'activated-opacity': 0.12,
    'pressed-opacity': 0.12,
    'dragged-opacity': 0.08,
    'theme-kbd': '#212529',
    'theme-on-kbd': '#FFFFFF',
    'theme-code': '#F5F5F5',
    'theme-on-code': '#000000',
  }
}

const TestTheme = {
  dark: false,
  colors: {
    background: '#191818E0',
    surface: '#FFFFFF',
    primary: '#1867C0',
    secondary: '#48A9A6',
    error: '#B00020',
    info: '#2196F3',
    success: '#4CAF50',
    warning: '#FB8C00',
    tertiary: '#AAAAAA',
    // Application specific colors
    'toolsbackground': '#FBEE32',
    'dialogbackground': '#FBEE32',
    'primary-button': '#7881EF',
    'secondary-button': '#00FEEC',
    'tertiary-button': '#C0C0C0',
    'danger-button': '#FE0000',
  },
  variables: {
    'border-color': '#000000',
    'border-opacity': 0.12,
    'high-emphasis-opacity': 0.87,
    'medium-emphasis-opacity': 0.60,
    'disabled-opacity': 0.38,
    'idle-opacity': 0.04,
    'hover-opacity': 0.04,
    'focus-opacity': 0.12,
    'selected-opacity': 0.08,
    'activated-opacity': 0.12,
    'pressed-opacity': 0.12,
    'dragged-opacity': 0.08,
    'theme-kbd': '#212529',
    'theme-on-kbd': '#FFFFFF',
    'theme-code': '#F5F5F5',
    'theme-on-code': '#000000',
  }
}



export default createVuetify({
  theme: {
    defaultTheme: 'LightTheme',
    themes: {
      LightTheme,
      DarkTheme,
      TestTheme
    },
  },
})
