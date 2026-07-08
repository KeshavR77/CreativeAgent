/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Editorial paper system — warm paper, ink, one accent.
        paper: '#F7F5F1',
        panel: '#FFFFFF',
        ink: {
          DEFAULT: '#1A1817',
          soft: '#403C38',
        },
        muted: '#8A857C',
        faint: '#B8B2A7',
        line: '#E5E1D8',
        accent: {
          DEFAULT: '#C6482E', // correction red — used sparingly
          soft: '#F6E7E2',
        },
        ok: '#3D6B4F',
        okSoft: '#E4EEE7',
        warn: '#8A6D1F',
        warnSoft: '#F5EDD8',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'Inter', 'Segoe UI', 'sans-serif'],
        serif: ['ui-serif', 'New York', 'Georgia', 'serif'],
        mono: ['ui-monospace', 'SF Mono', 'Menlo', 'monospace'],
      },
      letterSpacing: {
        kicker: '0.14em',
      },
    },
  },
  plugins: [],
};
