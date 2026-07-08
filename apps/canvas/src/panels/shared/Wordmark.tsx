/**
 * NLFR wordmark (redesign P3, board 1c): a 28px radius-9 teal square holding a
 * 14px white crosshair-node glyph, beside the two-line lockup. Inline SVG,
 * zero external assets.
 */
export function Wordmark() {
  return (
    <div className="wordmark" aria-label="NativeLink Agent Flight Recorder">
      <span className="wordmark-mark" aria-hidden="true">
        <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth={2} strokeLinecap="round">
          {/* crosshair-node: a centred node with four reach lines */}
          <circle cx={12} cy={12} r={3.4} fill="#ffffff" stroke="none" />
          <path d="M12 2.5V7" />
          <path d="M12 17V21.5" />
          <path d="M2.5 12H7" />
          <path d="M17 12H21.5" />
        </svg>
      </span>
      <span className="wordmark-lockup">
        <span className="wordmark-name">NLFR</span>
        <span className="wordmark-sub">NativeLink Agent Flight Recorder</span>
      </span>
    </div>
  );
}
