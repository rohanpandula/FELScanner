/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Single-accent taste-skill palette — electric blue, no purple, no gold.
        // Legacy "cinema" namespace retained to avoid breaking any v-bind class
        // references; all tokens remapped to the new neutrals/accent.
        accent: {
          DEFAULT: '#4d7cff',
          hover:   '#6b92ff',
          muted:   'rgba(77, 124, 255, 0.12)',
        },
        zinc: {
          50:  '#f4f4f5',
          100: '#e4e4e7',
          200: '#d4d4d8',
          300: '#a1a1aa',
          400: '#71717a',
          500: '#52525b',
          600: '#3f3f46',
          700: '#27272a',
          800: '#1c1c1f',
          900: '#141416',
          950: '#0c0c0e',
        },
        cinema: {
          black:           '#0c0c0e',
          charcoal:        '#141416',
          slate:           '#1c1c1f',
          gray:            '#71717a',
          white:           '#f4f4f5',
          gold:            '#4d7cff',   // legacy name -> electric blue
          'gold-dark':     '#3a67e6',
          violet:          '#4d7cff',
          'violet-bright': '#9bb4ff',
          burgundy:        '#d45473',
          wine:            '#b53d63',
        },
        success: '#3fa877',
        warning: '#d49a42',
        error:   '#d45473',
        info:    '#4d7cff',
      },
      fontFamily: {
        display: ['Geist', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        sans:    ['Geist', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono:    ['Geist Mono', 'JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        'card': '12px',
      },
      backdropBlur: {
        'card': '24px',
      },
    },
  },
  plugins: [],
}
