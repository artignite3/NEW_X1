// The ground seen from above: boundary, 30-yard circle, pitch and one shot.
// Used for empty states on Fixtures and the Simulator.
export default function OvalGraphic({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 320 180" className={`w-full max-w-sm ${className}`} aria-hidden>
      <ellipse cx="160" cy="90" rx="150" ry="82" fill="var(--color-panel)" stroke="var(--color-line-strong)" strokeWidth="1" />
      <ellipse cx="160" cy="90" rx="78" ry="42" fill="none" stroke="var(--color-line)" strokeWidth="1" strokeDasharray="3 4" />
      <rect x="152" y="70" width="16" height="40" rx="2" fill="var(--color-panel-hi)" stroke="var(--color-line-strong)" strokeWidth="1" />
      <path d="M160 104 C 128 64, 196 40, 262 50" fill="none" stroke="var(--color-accent)" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="160" cy="104" r="2.5" fill="var(--color-accent)" />
      <circle cx="262" cy="50" r="3" fill="none" stroke="var(--color-accent)" strokeWidth="1.5" />
    </svg>
  );
}
