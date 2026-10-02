/** Состояние кнопки сайдбара: покой, «раскрыть» (стрелка к концу строки), «свернуть». */
type SidebarGlyphVariant = "plain" | "expand" | "collapse";

interface SidebarGlyphProps {
  readonly variant: SidebarGlyphVariant;
  readonly size?: number;
}

/** Стрелка — одна polyline с общей вершиной: два отрезка с butt-концами не смыкались на острие. */
const ARROW_POINTS: Readonly<Record<SidebarGlyphVariant, string | null>> = {
  plain: null,
  expand: "10,6.6 13.5,9 10,11.4",
  collapse: "12.5,11.4 9,9 12.5,6.6",
};

/**
 * Глиф кнопки сворачивания сайдбара: панель с разделителем и стрелкой.
 * Сетка целая, 18 × 18, без crispEdges: тот подгонял штрих под пиксель и
 * рисовал скруглённые углы лесенкой. rx=2.8 при size=26 — около 4px, ступень
 * --radius-xs; единицы SVG не CSS-пиксели, поэтому прочитать токен отсюда нельзя.
 */
export function SidebarGlyph({ variant, size = 16 }: SidebarGlyphProps) {
  const arrow = ARROW_POINTS[variant];
  return (
    <svg
      width={`${size / 16}em`}
      height={`${size / 16}em`}
      viewBox="0 0 18 18"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="butt"
      strokeLinejoin="miter"
      aria-hidden="true"
      className="block"
    >
      <rect x="1" y="1" width="16" height="16" rx="2.8" />
      <line x1="6" y1="4.25" x2="6" y2="13.75" />
      {arrow === null ? null : (
        <polyline points={arrow} strokeLinejoin="round" strokeLinecap="round" />
      )}
    </svg>
  );
}
