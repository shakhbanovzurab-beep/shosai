"use client";

import { create } from "zustand";

import type { SettingsSection } from "../domain/sections";

type DialogState = {
  section: SettingsSection | null;
  /** Opens the dialog at a section, e.g. from the user menu. */
  open: (section?: SettingsSection) => void;
  close: () => void;
};

export const useSettingsDialog = create<DialogState>((set) => ({
  section: null,
  open: (section = "account") => set({ section }),
  close: () => set({ section: null }),
}));

/** Opens the settings dialog: at Account, or at the section given. */
export const useOpenSettings = () => useSettingsDialog((state) => state.open);
