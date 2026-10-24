import localFont from "next/font/local";

// Self-hosted (copied from Fontsource) so builds never depend on reaching
// Google Fonts. Latin only: every character the UI uses is in it.
export const publicSans = localFont({
  src: "./fonts/public-sans-latin-wght-normal.woff2",
  variable: "--font-public-sans",
  weight: "100 900",
  style: "normal",
  display: "swap",
  preload: true,
});

export const newsreader = localFont({
  src: "./fonts/newsreader-latin-wght-normal.woff2",
  variable: "--font-newsreader",
  weight: "200 800",
  style: "normal",
  display: "swap",
  preload: true,
});
