import { toast } from "sonner";

import { errorMessage } from "@/lib/errors";

import { supportApi } from "../api/support-api";
import type { TicketCategory, UpdateTicketRequest } from "../domain/contract";
import { useSupport } from "./support-store";
import type { SupportWords } from "./words";

/** Opens a ticket in the panel and fetches its thread (which marks it read); a cached thread shows at once. */
export function showTicket(t: SupportWords, id: string) {
  const { details, receive } = useSupport.getState();
  useSupport.setState({ selected: id, loadingId: details[id] ? null : id });
  supportApi.get(id).then(
    (ticket) => {
      receive(ticket);
      useSupport.setState((s) => (s.loadingId === id ? { loadingId: null } : s));
    },
    (error: unknown) => {
      useSupport.setState({ loadingId: null });
      toast.error(t("toasts.openFailed"), { description: errorMessage(error) });
    },
  );
}

/** Opens a new ticket and shows it in the panel. */
export async function openTicket(
  t: SupportWords,
  subject: string,
  category: TicketCategory,
  body: string,
  files: File[],
) {
  try {
    const ticket = await supportApi.create(subject, category, body, files);
    useSupport.getState().receive(ticket);
    showTicket(t, ticket.id);
    toast.success(t("toasts.opened", { number: String(ticket.number) }));
  } catch (error) {
    toast.error(t("toasts.openFailed"), { description: errorMessage(error) });
  }
}

/** Resolves or reopens, rates, or marks a ticket read or unread; `done` is announced once it is saved. */
export async function updateTicket(t: SupportWords, id: string, patch: UpdateTicketRequest, done?: string) {
  try {
    useSupport.getState().receive(await supportApi.update(id, patch));
    if (done) toast.success(done);
  } catch (error) {
    toast.error(t("toasts.updateFailed"), { description: errorMessage(error) });
  }
}

/** Sends your reply; resolves true when it was sent, so the draft is cleared only on success. */
export async function replyToTicket(t: SupportWords, id: string, body: string, files: File[]) {
  try {
    useSupport.getState().receive(await supportApi.reply(id, body, files));
    return true;
  } catch (error) {
    toast.error(t("toasts.sendFailed"), { description: errorMessage(error) });
    return false;
  }
}
