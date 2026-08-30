/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#ffffff',
        panel: '#ffffff',
        border: '#e7e5e4',
        accent: '#44403c',
      },
    },
  },
  plugins: [],
}
