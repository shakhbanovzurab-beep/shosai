import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { Kanban } from "@/features/kanban";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("kanban");
  return {
    title: t("meta.title"),
    description: t("meta.description"),
    alternates: {
      canonical: "/app/kanban",
    },
  };
}

interface PageProps {
  searchParams: Promise<{ board?: string | string[] }>;
}

export default async function Page({ searchParams }: PageProps) {
  const { board } = await searchParams;
  return <Kanban boardId={typeof board === "string" ? board : null} />;
}
