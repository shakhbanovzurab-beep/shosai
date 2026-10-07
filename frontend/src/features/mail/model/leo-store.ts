import { toast } from "sonner";
import { create } from "zustand";
import { useShallow } from "zustand/react/shallow";

import type { MailTriage } from "../domain/leo-insights";
import type { LeoOverrides } from "../domain/leo-triage";
import type { MailWords } from "./words";

type LeoStore = LeoOverrides & {
  /** The email whose draft is open for review, if any. */
  openDraftId: string | null;
};

/* The user's side of working with Leo: re-sorting emails, editing and discarding drafts. Kept in this
   browser session until the backend accepts this feedback. */
const useLeoStore = create<LeoStore>(() => ({ triage: {}, drafts: {}, discarded: {}, openDraftId: null }));

export function useLeoOverrides(): LeoOverrides {
  return useLeoStore(useShallow(({ triage, drafts, discarded }) => ({ triage, drafts, discarded })));
}

export function useOpenDraftId() {
  return useLeoStore((state) => state.openDraftId);
}

/** Leo actions, safe to call from handlers. */
export const leoActions = {
  openDraft: (mailId: string) => useLeoStore.setState({ openDraftId: mailId }),
  closeDraft: () => useLeoStore.setState({ openDraftId: null }),
  editDraft: (mailId: string, text: string) =>
    useLeoStore.setState((state) => ({ drafts: { ...state.drafts, [mailId]: text } })),
  /** Drops the draft, with an Undo that brings it back as it was. */
  discardDraft: (mailId: string, { leo, common }: MailWords) => {
    useLeoStore.setState((state) => ({
      discarded: { ...state.discarded, [mailId]: true },
      openDraftId: state.openDraftId === mailId ? null : state.openDraftId,
    }));
    toast(leo("draft.discarded"), {
      action: {
        label: common("actions.undo"),
        onClick: () =>
          useLeoStore.setState((state) => {
            const { [mailId]: _restored, ...discarded } = state.discarded;
            return { discarded };
          }),
      },
    });
  },
  /** Re-sorts an email; choosing Leo's own triage again clears the correction. */
  correctTriage: (mailId: string, triage: MailTriage, leoTriage: MailTriage | null) =>
    useLeoStore.setState((state) => {
      const { [mailId]: _previous, ...rest } = state.triage;
      return { triage: triage === leoTriage ? rest : { ...rest, [mailId]: triage } };
    }),
};
