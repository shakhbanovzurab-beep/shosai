import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { parseLibraryQuery, TeamMeetingsScreen } from "@/features/workspace";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("workspace");
  return { title: t("meta.meetings"), robots: { index: false } };
}

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function Page({ searchParams }: PageProps) {
  return <TeamMeetingsScreen initialQuery={parseLibraryQuery(await searchParams)} />;
}
