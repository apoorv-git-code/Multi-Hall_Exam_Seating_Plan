/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: { sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'] },
      boxShadow: { card: '0 1px 2px rgba(15,23,42,.06), 0 1px 3px rgba(15,23,42,.08)' },
    },
  },
  plugins: [],
}
