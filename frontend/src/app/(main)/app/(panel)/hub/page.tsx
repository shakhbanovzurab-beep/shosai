import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { HubsScreen, parseHubsFilter } from "@/features/hub";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("hub");
  return {
    title: t("list.title"),
    description: t("list.lead"),
    alternates: {
      canonical: "/app/hub",
    },
  };
}

interface PageProps {
  searchParams: Promise<{ show?: string | string[] }>;
}

export default async function Page({ searchParams }: PageProps) {
  const { show } = await searchParams;
  return <HubsScreen filter={parseHubsFilter(show)} />;
}
