import { z } from "zod";

import { JsonResponse } from "@/mocks/runtime";

import { comboProblem, effectiveBindings, HOTKEY_IDS, type HotkeyBindings, isValidCombo } from "../domain/hotkeys";
import type { UserSettings } from "../domain/settings-contract";
import { getSettings, patchSettings } from "./demo-settings";
import { firstIssue, type Problem, readJson, refuse, refuseCombo } from "./problems";

// Messages are problem codes, worded for the request when it is refused (see ./problems).
const FIXABLE = ["hotkeyUnsupported"] as const satisfies Problem[];
type Fixable = (typeof FIXABLE)[number];

const patchSchema = z
  .object({
    hotkeys: z.partialRecord(
      z.enum(HOTKEY_IDS),
      z
        .string()
        .refine(isValidCombo, "hotkeyUnsupported" satisfies Fixable)
        .nullable(),
    ),
  })
  .partial()
  .strict();

/** The first shortcut that is reserved by the system or taken by another command. */
function hotkeysProblem(hotkeys: HotkeyBindings) {
  const bindings = effectiveBindings(hotkeys);
  for (const id of HOTKEY_IDS) {
    const combo = hotkeys[id];
    if (combo) {
      const problem = comboProblem(combo, id, bindings);
      if (problem) return problem;
    }
  }
  return null;
}

/** /api/settings: the hotkeys capture still serves from mocks (Leo's are agent's, memory's switch is memory's). */
export const settingsRoute = {
  async GET(_request: Request) {
    return JsonResponse.json<UserSettings>(getSettings());
  },

  /** Saves any subset of the preferences; the dialog sends one field at a time as it changes. */
  async PATCH(request: Request) {
    const body = patchSchema.safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error, FIXABLE), 422);
    const problem = body.data.hotkeys ? hotkeysProblem(body.data.hotkeys) : null;
    if (problem) return refuseCombo(problem);
    return JsonResponse.json<UserSettings>(patchSettings(body.data));
  },
};
