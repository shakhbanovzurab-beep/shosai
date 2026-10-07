import createNextIntlPlugin from "next-intl/plugin";

import { readdirSync } from "node:fs";

const ENGLISH_MESSAGES = "./src/i18n/messages/en";

// The language of each request and its messages (src/i18n/request.ts). The English catalogs, the source,
// also get a type declaration each, so `t("key", args)` is checked against the message's ICU arguments.
const withNextIntl = createNextIntlPlugin({
  requestConfig: "./src/i18n/request.ts",
  experimental: {
    createMessagesDeclaration: readdirSync(ENGLISH_MESSAGES)
      .filter((file) => file.endsWith(".json"))
      .map((file) => `${ENGLISH_MESSAGES}/${file}`),
  },
});

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactCompiler: true,
  compiler: {
    removeConsole: process.env.NODE_ENV === "production",
  },
  async redirects() {
    return [
      { source: "/", destination: "/app/productivity", permanent: false },
      { source: "/app", destination: "/app/productivity", permanent: false },
      { source: "/admin", destination: "/admin/dashboard", permanent: true },
      // Screens that became tabs: old links open the matching tab.
      { source: "/admin/analytics", destination: "/admin/dashboard?tab=analytics", permanent: false },
      { source: "/admin/crm", destination: "/admin/dashboard?tab=crm", permanent: false },
      { source: "/admin/crm-v1", destination: "/admin/dashboard?tab=crm-v1", permanent: false },
      { source: "/app/studio/context", destination: "/app/studio", permanent: false },
      { source: "/app/studio/prompts", destination: "/app/studio?tab=prompts", permanent: false },
      { source: "/app/studio/models", destination: "/app/studio?tab=models", permanent: false },
      // Old addresses: the user panel moved from /dashboard to /app and the standalone mail to /app/inbox.
      { source: "/dashboard", destination: "/app/productivity", permanent: false },
      { source: "/dashboard/:path*", destination: "/app/:path*", permanent: false },
      { source: "/mail", destination: "/app/inbox", permanent: false },
      // The single team workspace became one or more workspaces, each under its own slug.
      { source: "/app/team", destination: "/app/w", permanent: false },
      { source: "/app/team/:path*", destination: "/app/w", permanent: false },
    ];
  },
};

export default withNextIntl(nextConfig);
