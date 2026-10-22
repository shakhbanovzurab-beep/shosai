"use client";

import { create } from "zustand";

import type { SettingsSection } from "../domain/sections";

/** A group inside a section the dialog scrolls to when it opens, e.g. Messengers from the workspace hint. */
export type SettingsAnchor = "messengers";

type DialogState = {
  section: SettingsSection | null;
  anchor: SettingsAnchor | null;
  /** Opens the dialog at a section, e.g. from the user menu; another section drops the anchor. */
  open: (section?: SettingsSection, anchor?: SettingsAnchor) => void;
  close: () => void;
};

export const useSettingsDialog = create<DialogState>((set) => ({
  section: null,
  anchor: null,
  open: (section = "account", anchor) => set({ section, anchor: anchor ?? null }),
  close: () => set({ section: null, anchor: null }),
}));

/** Opens the settings dialog: at Account, or at the section (and the group in it) given. */
export const useOpenSettings = () => useSettingsDialog((state) => state.open);
