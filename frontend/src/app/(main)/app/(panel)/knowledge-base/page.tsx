import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { KnowledgeBaseScreen, type KnowledgeBaseTab } from "@/features/knowledge-base";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("knowledgeBase");
  return {
    title: t("meta.title"),
    description: t("meta.description"),
    alternates: {
      canonical: "/app/knowledge-base",
    },
  };
}

interface PageProps {
  searchParams: Promise<{ tab?: string | string[] }>;
}

export default async function Page({ searchParams }: PageProps) {
  const { tab } = await searchParams;
  const initialTab: KnowledgeBaseTab = tab === "sources" || tab === "workspaces" ? tab : "files";

  return <KnowledgeBaseScreen initialTab={initialTab} />;
}
