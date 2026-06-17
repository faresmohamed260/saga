/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        saga: {
          bg: "#111110",
          panel: "#161616",
          line: "#2a2a2a",
          text: "#f2f2f2",
        },
      },
    },
  },
  plugins: [],
};

