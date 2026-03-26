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
        cinema: {
          black: '#0a0a0f',
          charcoal: '#1a1a24',
          slate: '#2d2d3d',
          gray: '#6b6b7f',
          white: '#f5f5f7',
          gold: '#d4af37',
          'gold-dark': '#b8941f',
          violet: '#7c3aed',
          'violet-bright': '#a78bfa',
          burgundy: '#8b1538',
          wine: '#6b1129',
        },
        success: '#10b981',
        warning: '#f59e0b',
        error: '#8b1538',
        info: '#3b82f6',
      },
      fontFamily: {
        display: ['Cinzel', 'serif'],
        sans: ['Outfit', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Consolas', 'Monaco', 'monospace'],
      },
      borderRadius: {
        'card': '16px',
      },
      backdropBlur: {
        'card': '20px',
      },
    },
  },
  plugins: [],
}
