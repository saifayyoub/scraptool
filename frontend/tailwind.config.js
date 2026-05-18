/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./*.{html,js}"],
  theme: {
    extend: {
      colors: {
        gray: {
          950: '#0a0a0a',
          900: '#111111',
          800: '#222222',
        }
      }
    },
  },
  plugins: [],
}
