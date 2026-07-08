import type { Confidence } from "../../../types";
import { confidenceMeta } from "./copy";

/**
 * confidence → neutral 3-bar meter (DESIGN-SYSTEM.md §2). NEVER coloured by
 * source hue: filled bars use --meter-filled (--n7), empty use --meter-empty
 * (hairline), so it reads in pure monochrome. unknown = 0 filled + mono "?".
 */
const BAR_HEIGHTS = {
  sm: [4, 6.5, 9],
  md: [5, 8, 11],
} as const;

const BAR_WIDTH = 3.2;
const BAR_GAP = 1.5;

export function ConfidenceMeter({
  confidence,
  size = "sm",
  title,
}: {
  confidence: Confidence;
  size?: "sm" | "md";
  title?: string | null;
}) {
  const meta = confidenceMeta(confidence);
  const heights = BAR_HEIGHTS[size];
  const maxHeight = heights[heights.length - 1];
  const width = heights.length * BAR_WIDTH + (heights.length - 1) * BAR_GAP;
  const tip = title === undefined ? meta.tooltip : title;

  return (
    <span
      className="confidence-meter"
      data-confidence={confidence}
      title={tip ?? undefined}
      aria-label={`confidence ${confidence}`}
    >
      <svg
        width={width}
        height={maxHeight}
        viewBox={`0 0 ${width} ${maxHeight}`}
        role="img"
        aria-hidden="true"
        focusable="false"
      >
        {heights.map((height, index) => (
          <rect
            key={index}
            className={index < meta.filled ? "confidence-bar--filled" : "confidence-bar--empty"}
            x={index * (BAR_WIDTH + BAR_GAP)}
            y={maxHeight - height}
            width={BAR_WIDTH}
            height={height}
            rx={1}
          />
        ))}
      </svg>
      {meta.showUnknown && <span className="confidence-unknown">?</span>}
    </span>
  );
}
