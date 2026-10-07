import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { STUDIO_TABS, StudioScreen, type StudioTab } from "@/features/studio";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("studio");
  return {
    title: t("meta.title"),
    description: t("meta.description"),
    alternates: {
      canonical: "/app/studio",
    },
  };
}

interface PageProps {
  searchParams: Promise<{ tab?: string | string[] }>;
}

export default async function Page({ searchParams }: PageProps) {
  const { tab } = await searchParams;
  const initialTab: StudioTab = STUDIO_TABS.find((t) => t === tab) ?? "context";

  return <StudioScreen initialTab={initialTab} />;
}
