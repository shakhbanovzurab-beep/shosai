import type { useFormatter, useTranslations } from "use-intl";

import type { FocusPreset } from "../domain/focus/timer";

/*
 * The catalogs the slice's plain functions word things with. They aren't components, so the Client
 * Component that calls one passes its translator (and formatter) in.
 */

export type FocusWords = ReturnType<typeof useTranslations<"productivityFocus">>;
export type SkylineWords = ReturnType<typeof useTranslations<"productivitySkyline">>;
export type Formatter = ReturnType<typeof useFormatter>;

/** Catalog keys of the presets. Their ids are saved in the browser, so they keep their spelling. */
const PRESET_KEYS = {
  pomodoro: "pomodoro",
  fifty: "fifty",
  "fifty-two": "fiftyTwo",
  "deep-work": "deepWork",
} as const satisfies Record<FocusPreset["id"], string>;

/** The rhythm's name: "Pomodoro", "Deep work". */
export const presetName = (t: FocusWords, preset: FocusPreset) =>
  t(`presets.${PRESET_KEYS[preset.id]}.name`, { focus: preset.focusMin, pause: preset.breakMin });

/** Its lengths and what it is good for: "25 min focus, 5 min break, 15 min after every 4 sessions. Good for…". */
export function presetHint(t: FocusWords, format: Formatter, preset: FocusPreset) {
  const minutes = (count: number) => format.number(count, "minutes");
  return t(`presets.${PRESET_KEYS[preset.id]}.hint`, {
    focus: minutes(preset.focusMin),
    pause: minutes(preset.breakMin),
    longBreak: minutes(preset.longBreakMin),
    every: preset.longEvery,
  });
}
