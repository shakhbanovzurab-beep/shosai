import type { MetadataRoute } from "next";

import { SITE_URL } from "@/config/site-url";

const PUBLIC_ROUTES = [
  "/app/productivity",
  "/app/file-manager",
  "/app/mail",
  "/app/calendar",
  "/app/kanban",
  "/app/hub",
  "/app/studio",
  "/app/meetings",
  "/app/notes",
  "/app/knowledge-base",
  "/app/download",
  "/app/inbox",
] as const;

export default function sitemap(): MetadataRoute.Sitemap {
  if (!SITE_URL) return [];
  return PUBLIC_ROUTES.map((route) => ({
    url: `${SITE_URL}${route}`,
  }));
}
