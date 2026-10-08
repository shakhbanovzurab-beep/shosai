import { z } from "zod";

import { isSubscriptionTextModel } from "@/features/studio/mocks/demo-models";
import { LANGUAGES } from "@/lib/language";
import { JsonResponse } from "@/mocks/runtime";

import { comboProblem, effectiveBindings, HOTKEY_IDS, type HotkeyBindings, isValidCombo } from "../domain/hotkeys";
import { NAME_MAX, RESPONSE_LENGTHS, type UserSettings, WORK_ROLES } from "../domain/settings-contract";
import { getSettings, patchSettings } from "./demo-settings";
import { firstIssue, type Problem, readJson, refuse, refuseCombo } from "./problems";

const languages = ["auto", ...LANGUAGES.map((l) => l.code)] as [string, ...string[]];

// Messages are problem codes, worded for the request when it is refused (see ./problems).
const FIXABLE = ["nameRequired", "hotkeyUnsupported"] as const satisfies Problem[];
type Fixable = (typeof FIXABLE)[number];

const patchSchema = z
  .object({
    full_name: z
      .string()
      .trim()
      .min(1, "nameRequired" satisfies Fixable)
      .max(NAME_MAX),
    display_name: z.string().trim().max(NAME_MAX),
    work_role: z.enum(WORK_ROLES),
    improve_models: z.boolean(),
    share_location: z.boolean(),
    leo_model: z.string().max(200),
    response_language: z.enum(languages),
    response_length: z.enum(RESPONSE_LENGTHS),
    web_search: z.boolean(),
    voice_mode: z.boolean(),
    knowledge_base_search: z.boolean(),
    connected_services_search: z.boolean(),
    memory_enabled: z.boolean(),
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

/** /api/settings: the user's preferences. */
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
    const model = body.data.leo_model;
    if (model && model !== "auto" && !isSubscriptionTextModel(model)) return refuse("modelNotOnPlan", 422);
    return JsonResponse.json<UserSettings>(patchSettings(body.data));
  },
};
