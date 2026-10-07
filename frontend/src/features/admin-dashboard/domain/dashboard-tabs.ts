// A plain module (no React, no "use client") so the server page can parse `?tab=` with the same ids the client tabs use.
export const DASHBOARD_TABS = [
  { id: "analytics", label: "Аналитика" },
  { id: "crm", label: "CRM" },
  { id: "crm-v1", label: "CRM v1" },
] as const;

export type DashboardTab = (typeof DASHBOARD_TABS)[number]["id"];

export function parseDashboardTab(value: unknown): DashboardTab {
  return DASHBOARD_TABS.find((tab) => tab.id === value)?.id ?? "analytics";
}
