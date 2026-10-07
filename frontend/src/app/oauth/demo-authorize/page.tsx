import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { ConnectorConsentDemo } from "@/features/settings/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("settingsConnectors");
  return {
    title: t("consent.metaTitle"),
    robots: { index: false, follow: false },
  };
}

interface PageProps {
  searchParams: Promise<{ connector?: string; state?: string }>;
}

/** The demo's stand-in for a provider's OAuth consent screen while no backend is configured. */
export default async function Page({ searchParams }: PageProps) {
  const { connector = "", state = "" } = await searchParams;
  return <ConnectorConsentDemo connector={connector} state={state} />;
}
