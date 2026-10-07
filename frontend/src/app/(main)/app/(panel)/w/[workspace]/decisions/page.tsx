import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { DecisionsScreen, parseLibraryQuery } from "@/features/workspace";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("workspace");
  return { title: t("meta.decisions"), robots: { index: false } };
}

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function Page({ searchParams }: PageProps) {
  return <DecisionsScreen initialQuery={parseLibraryQuery(await searchParams)} />;
}
