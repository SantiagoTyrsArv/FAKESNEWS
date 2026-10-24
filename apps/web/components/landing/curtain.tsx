// Three paper strips (orange, blue, ink) covering the landing on its first
// visit in the session. Hidden by default; shown from the first paint by CSS
// under html.motion.curtain (set by the inline script in app/layout.tsx on
// desktop pointers) and lifted (≤ 0.9 s) by useLandingMotion. It never takes
// clicks.
export function Curtain() {
  return (
    <div
      data-curtain
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-50 hidden"
    >
      <span className="flex-1 bg-collage-orange" />
      <span className="flex-1 bg-collage-blue" />
      <span className="flex-1 bg-ink" />
    </div>
  );
}
