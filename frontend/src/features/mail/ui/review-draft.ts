import { leoActions } from "../model/leo-store";

/** The id of the draft's text field, so the open action can move focus into it. */
export const draftFieldId = (mailId: string) => `leo-draft-${mailId}`;

/** Opens Leo's draft for the email and puts the caret in it. */
export function reviewDraft(mailId: string) {
  leoActions.openDraft(mailId);
  // The editor mounts with this update, so focus it on the next frame.
  requestAnimationFrame(() => document.getElementById(draftFieldId(mailId))?.focus());
}
