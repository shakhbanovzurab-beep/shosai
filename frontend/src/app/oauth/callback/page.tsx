import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { OAuthCallback } from "@/features/settings";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("settingsConnectors");
  return {
    title: t("callback.metaTitle"),
    robots: { index: false, follow: false },
  };
}

interface PageProps {
  searchParams: Promise<{ connector?: string; status?: string; error?: string }>;
}

/** Where the OAuth popup lands after the provider's consent screen; it reports back and closes. */
export default async function Page({ searchParams }: PageProps) {
  const { connector = "", status, error } = await searchParams;
  const result = status === "connected" || status === "denied" ? status : "error";
  return <OAuthCallback connector={connector} status={result} error={error ?? null} />;
}
