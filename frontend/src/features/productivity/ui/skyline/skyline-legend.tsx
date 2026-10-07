import { cn } from "cn";
import { useTranslations } from "next-intl";

/** The activity levels, from an empty day (0) to the busiest (4). */
const LEVELS = ["none", "light", "moderate", "heavy", "heaviest"] as const;

/**
 * Less → More swatches, in the page direction. Hovering or focusing one dims every other level on the chart.
 */
export function SkylineLegend({
  swatches,
  activeLevel,
  onLevelChange,
}: {
  swatches: string[];
  activeLevel: number;
  onLevelChange: (level: number) => void;
}) {
  const t = useTranslations("productivitySkyline");
  return (
    <ul
      aria-label={t("levels.label")}
      className="m-0 flex list-none items-center gap-1 p-0 text-muted-foreground text-xs"
      onMouseLeave={() => onLevelChange(-1)}
    >
      <li aria-hidden="true" className="me-1">
        {t("levels.less")}
      </li>
      {LEVELS.map((level, index) => {
        const name = t(`levels.${level}`);
        return (
          <li key={level}>
            <button
              type="button"
              aria-label={name}
              aria-pressed={activeLevel === index}
              title={name}
              onMouseEnter={() => onLevelChange(index)}
              onFocus={() => onLevelChange(index)}
              onBlur={() => onLevelChange(-1)}
              className={cn(
                "block size-3 cursor-default rounded-[3px] border border-foreground/10 transition-transform duration-150 focus-visible:outline-2 focus-visible:outline-ring focus-visible:outline-offset-2 motion-reduce:transition-none",
                activeLevel === index && "scale-125",
              )}
              style={{ background: swatches[index] }}
            />
          </li>
        );
      })}
      <li aria-hidden="true" className="ms-1">
        {t("levels.more")}
      </li>
    </ul>
  );
}
