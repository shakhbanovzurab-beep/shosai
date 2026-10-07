import type { Formatters, StatBlock } from "../../domain/skyline/format";
import type { SkylineWords } from "../../model/words";

/** A headline number as shown: its label, the number, its unit and its dates, all in the interface language. */
export type StatView = { id: StatBlock["id"]; label: string; value: string; unit: string; sub: string };

export const statViews = (blocks: StatBlock[], t: SkylineWords, fmt: Formatters): StatView[] =>
  blocks.map(({ id, count, unit, dates }) => ({
    id,
    label: t(`stats.${id}`),
    value: fmt.number(count),
    unit: t(`units.${unit}`, { count }),
    sub: dates ?? "—",
  }));
