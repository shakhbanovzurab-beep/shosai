import {
  MARK_FILL,
  MARK_FONT,
  MARK_FONT_SIZE,
  MARK_INK,
  MARK_RADIUS,
  MARK_TEXT_STROKE,
  MARK_TILE,
  MARK_TILE_STROKE,
  MARK_TILES,
  MARK_VIEW_MIN,
  MARK_VIEW_SIZE,
} from "@/core/lib/brand/mark";

interface LogoProps {
  readonly size?: number;
}

const VIEW_BOX = `${MARK_VIEW_MIN} ${MARK_VIEW_MIN} ${MARK_VIEW_SIZE} ${MARK_VIEW_SIZE}`;

/** Логотип Whisperer — фирменный знак из `core/lib/brand/mark`, тот же, что у фавикона. */
export function Logo({ size = 28 }: LogoProps) {
  return (
    <svg width={size} height={size} viewBox={VIEW_BOX} role="img" aria-label="Whisperer" className="shrink-0">
      <g fontFamily={MARK_FONT} fontWeight={900} fill={MARK_INK} stroke={MARK_INK} paintOrder="stroke">
        {MARK_TILES.map((tile) => (
          <g key={`${tile.letter}-${tile.x}-${tile.y}`}>
            <rect
              x={tile.x}
              y={tile.y}
              width={MARK_TILE}
              height={MARK_TILE}
              rx={MARK_RADIUS}
              fill={MARK_FILL}
              stroke={MARK_INK}
              strokeWidth={MARK_TILE_STROKE}
            />
            <text
              x={tile.x + MARK_TILE / 2}
              y={tile.y + MARK_TILE / 2}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={MARK_FONT_SIZE}
              strokeWidth={MARK_TEXT_STROKE}
            >
              {tile.letter}
            </text>
          </g>
        ))}
      </g>
    </svg>
  );
}
