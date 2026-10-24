// Three paper strips (orange, blue, ink) covering the landing on its first
// visit in the session. Hidden by default: useLandingMotion shows it and lifts
// it (≤ 0.9 s) only when onceInSession("fn-curtain") and motion is allowed.
// It never takes clicks.
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
