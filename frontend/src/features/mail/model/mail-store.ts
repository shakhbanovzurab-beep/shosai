import { toast } from "sonner";
import { create } from "zustand";

import { mails as initialMails } from "../data/mails";
import type { Mail, MailFolder } from "../domain/mail";
import type { MailWords } from "./words";

type MailItemsStore = {
  items: Mail[];
  update: (id: string, patch: (mail: Mail) => Partial<Mail>) => void;
  replaceAll: (items: Mail[]) => void;
};

const useMailItemsStore = create<MailItemsStore>((set) => ({
  items: initialMails,
  update: (id, patch) =>
    set((state) => ({ items: state.items.map((mail) => (mail.id === id ? { ...mail, ...patch(mail) } : mail)) })),
  replaceAll: (items) => set({ items }),
}));

/** Every label used anywhere in the mailbox, for the "Labels" submenu. */
export const knownLabels = [...new Set(initialMails.flatMap((mail) => mail.labels))].toSorted();

export function useMailItems() {
  return useMailItemsStore((state) => state.items);
}

/** Mail actions, shared by the right-click menu and the inbox's "more" menu. Safe to call from handlers. */
export const mailActions = {
  toggleRead: (id: string) => useMailItemsStore.getState().update(id, (m) => ({ isRead: !m.isRead })),
  markRead: (id: string) => useMailItemsStore.getState().update(id, () => ({ isRead: true })),
  togglePinned: (id: string) => useMailItemsStore.getState().update(id, (m) => ({ isPinned: !m.isPinned })),
  togglePriority: (id: string) => useMailItemsStore.getState().update(id, (m) => ({ isPriority: !m.isPriority })),
  toggleLabel: (id: string, label: string) =>
    useMailItemsStore.getState().update(id, (m) => ({
      labels: m.labels.includes(label) ? m.labels.filter((l) => l !== label) : [...m.labels, label],
    })),
  copySender: (mail: Mail, { mail: t }: MailWords) =>
    navigator.clipboard.writeText(mail.from.email).then(
      () => toast.success(t("toasts.senderCopied", { email: mail.from.email })),
      () => toast.error(t("toasts.senderCopyFailed")),
    ),
  /** Sends a reply from the inbox. Sending is local until the mail backend exists; Undo takes it back. */
  sendReply: (mail: Mail, { mail: t, common }: MailWords, onUndo?: () => void) => {
    useMailItemsStore.getState().update(mail.id, () => ({ repliedAt: new Date().toISOString(), isRead: true }));
    toast.success(t("toasts.replySent", { name: mail.from.name }), {
      action: {
        label: common("actions.undo"),
        onClick: () => {
          useMailItemsStore.getState().update(mail.id, () => ({ repliedAt: mail.repliedAt }));
          onUndo?.();
        },
      },
    });
  },
  /** Archives several messages at once, with one Undo for all of them. */
  archiveMany: (ids: readonly string[], { mail: t, common }: MailWords) => {
    const { items, replaceAll } = useMailItemsStore.getState();
    const targets = new Set(ids);
    const count = items.filter((mail) => targets.has(mail.id) && mail.folder !== "archive").length;
    if (count === 0) return;
    replaceAll(items.map((mail): Mail => (targets.has(mail.id) ? { ...mail, folder: "archive" } : mail)));
    toast(t("toasts.archived", { count }), {
      action: { label: common("actions.undo"), onClick: () => replaceAll(items) },
    });
  },
  /** Moves a message out of the inbox (or back), with an Undo that restores the whole mailbox as it was. */
  moveTo: (id: string, folder: MailFolder, { mail: t, common }: MailWords) => {
    const { items, update, replaceAll } = useMailItemsStore.getState();
    const mail = items.find((m) => m.id === id);
    if (!mail || mail.folder === folder) return;
    update(id, () => ({ folder }));
    toast(t("toasts.moved", { subject: mail.subject, folder }), {
      action: { label: common("actions.undo"), onClick: () => replaceAll(items) },
    });
  },
};
