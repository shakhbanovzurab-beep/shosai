/** The settings dialog's sections, in the order its navigation lists them. */
const SETTINGS_SECTIONS = [
  "account",
  "privacy",
  "billing",
  "usage",
  "leo",
  "mcp",
  "memory",
  "connectors",
  "hotkeys",
] as const;
export type SettingsSection = (typeof SETTINGS_SECTIONS)[number];
