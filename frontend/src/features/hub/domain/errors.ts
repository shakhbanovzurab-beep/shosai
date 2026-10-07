/* Error codes the Hub API answers with, `{ "detail": { "code", "message" } }`. The client words them itself. */

export const HUB_ERROR_CODES = [
  "name_taken",
  "name_too_short",
  "name_too_long",
  "too_many_hubs",
  "not_found",
  "hub_archived",
  "no_board",
  "no_hub",
  "board_gone",
  "invalid",
] as const;

export type HubErrorCode = (typeof HUB_ERROR_CODES)[number] | "network" | "unknown";

export type ErrorBody = { detail: { code: string; message: string } };

export const isHubErrorCode = (value: unknown): value is HubErrorCode =>
  typeof value === "string" && (HUB_ERROR_CODES as readonly string[]).includes(value);

/** Why a task from a meeting couldn't go to a board, and the one action that fixes each. */
export const APPLY_REFUSALS = ["no_board", "no_hub", "hub_archived", "board_gone"] as const;
export type ApplyRefusal = (typeof APPLY_REFUSALS)[number];

export type RefusalFix = "choose_board" | "file_meeting" | "restore_hub";

export const refusalFix: Record<ApplyRefusal, RefusalFix> = {
  no_board: "choose_board",
  board_gone: "choose_board",
  no_hub: "file_meeting",
  hub_archived: "restore_hub",
};

/** The codes the create and rename forms show under the name field. */
export const NAME_ERRORS = ["name_taken", "name_too_short", "name_too_long", "too_many_hubs"] as const;
export type NameError = (typeof NAME_ERRORS)[number];

export const isNameError = (code: HubErrorCode): code is NameError => (NAME_ERRORS as readonly string[]).includes(code);
