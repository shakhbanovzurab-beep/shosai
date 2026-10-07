"use client";

import { create } from "zustand";

type InviteDialogState = { open: boolean; setOpen: (open: boolean) => void };

/**
 * The invite dialog is mounted once for all Team pages, so the switcher, Home and Members open the
 * same one. Asking from the Personal scope opens it as soon as a Team page shows.
 */
export const useInviteDialog = create<InviteDialogState>((set) => ({
  open: false,
  setOpen: (open) => set({ open }),
}));

export const openInviteDialog = () => useInviteDialog.getState().setOpen(true);
