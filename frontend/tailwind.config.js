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
        background: 'var(--background)',
        foreground: 'var(--foreground)',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        accent: {
          DEFAULT: 'var(--accent-color)',
          foreground: 'var(--accent-foreground, white)',
        },
        panel: 'var(--panel)',
        border: 'var(--border)',
        muted: 'var(--muted)',
        input: 'var(--input)',
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
