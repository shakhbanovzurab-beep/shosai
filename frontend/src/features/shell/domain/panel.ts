export type Panel = "dashboard" | "admin";

export const panelHomeUrls: Record<Panel, string> = {
  dashboard: "/app/productivity",
  admin: "/admin/dashboard",
};
