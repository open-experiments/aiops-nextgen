/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        severity: {
          critical: '#ef4444',
          warning: '#f59e0b',
          info: '#3b82f6',
        },
        status: {
          online: '#22c55e',
          offline: '#ef4444',
          degraded: '#f59e0b',
          unknown: '#6b7280',
        },
      },
    },
  },
  plugins: [],
};
