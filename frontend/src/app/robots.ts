import type { MetadataRoute } from "next";

import { SITE_URL } from "@/config/site-url";

// Search and AI crawlers each get their own block, so ones that read only their named block see the rules.
const CRAWLERS = [
  "*",
  "OAI-SearchBot",
  "Claude-SearchBot",
  "Amzn-SearchBot",
  "GPTBot",
  "ClaudeBot",
  "Claude-Web",
  "anthropic-ai",
  "Google-Extended",
  "Amazonbot",
  "Bytespider",
  "CCBot",
  "Applebot-Extended",
];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: CRAWLERS.map((userAgent) => ({
      userAgent,
      allow: "/",
      disallow: "/api/",
      other: { "Content-Signal": "ai-train=yes, search=yes, ai-input=yes" },
    })),
    sitemap: SITE_URL ? `${SITE_URL}/sitemap.xml` : undefined,
  };
}
