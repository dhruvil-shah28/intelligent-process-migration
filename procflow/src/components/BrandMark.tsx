export function BrandMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" aria-hidden="true">
      <rect x="5" y="12" width="18" height="40" fill="#0a0a0a" stroke="#33ff00" strokeWidth="2" />
      <rect x="41" y="12" width="18" height="40" fill="#0a0a0a" stroke="#33ff00" strokeWidth="2" />
      <path d="M23 32h16m-6-7 7 7-7 7" stroke="#ffb000" strokeWidth="3" strokeLinecap="square" strokeLinejoin="miter" />
      <circle cx="14" cy="23" r="2" fill="#33ff00" /><circle cx="50" cy="23" r="2" fill="#33ff00" />
    </svg>
  );
}
