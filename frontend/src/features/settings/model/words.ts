import type { useTranslations } from "use-intl";

/*
 * The catalogs the model's actions word their toasts with. Actions are plain functions, so the Client
 * Component that calls one passes its translator in (`useTranslations("settings")` and so on).
 */

export type SettingsWords = ReturnType<typeof useTranslations<"settings">>;
export type BillingWords = ReturnType<typeof useTranslations<"settingsBilling">>;
export type UsageWords = ReturnType<typeof useTranslations<"settingsUsage">>;
export type McpWords = ReturnType<typeof useTranslations<"settingsMcp">>;
export type MemoryWords = ReturnType<typeof useTranslations<"settingsMemory">>;
