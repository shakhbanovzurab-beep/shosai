"use client";

import { useTranslations } from "use-intl";

import { HUB_NAME_MAX, HUB_NAME_MIN } from "../domain/contract";
import type { HubErrorCode } from "../domain/errors";

/*
 * The catalogs the model's actions word their toasts with. Actions are plain functions, so the Client
 * Component that calls one passes the words in, from `useHubWords()`.
 */

export type HubWords = ReturnType<typeof useTranslations<"hub">>;
export type HubBlockWords = ReturnType<typeof useTranslations<"hubBlocks">>;
export type HubMeetingWords = ReturnType<typeof useTranslations<"hubMeetings">>;
export type HubApiWords = ReturnType<typeof useTranslations<"hubApi">>;
export type CommonWords = ReturnType<typeof useTranslations<"common">>;

export interface ActionWords {
  hub: HubWords;
  blocks: HubBlockWords;
  meetings: HubMeetingWords;
  api: HubApiWords;
  common: CommonWords;
}

/** Every catalog an action may need, for passing to the functions in ./hub-actions and its siblings. */
export function useHubWords(): ActionWords {
  return {
    hub: useTranslations("hub"),
    blocks: useTranslations("hubBlocks"),
    meetings: useTranslations("hubMeetings"),
    api: useTranslations("hubApi"),
    common: useTranslations("common"),
  };
}

/** What a refusal means for the person, from the code the server answered with. */
export function errorText(api: HubApiWords, code: HubErrorCode): string {
  if (code === "name_too_short") return api("errors.name_too_short", { min: HUB_NAME_MIN });
  if (code === "name_too_long") return api("errors.name_too_long", { max: HUB_NAME_MAX });
  return api(`errors.${code}`);
}

/** `errorText` for a component: the words for any code the Hub's API answers with. */
export function useErrorText() {
  const api = useTranslations("hubApi");
  return (code: HubErrorCode) => errorText(api, code);
}
