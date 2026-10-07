import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { MembersScreen } from "@/features/workspace";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("workspace");
  return { title: t("meta.members"), robots: { index: false } };
}

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function Page({ searchParams }: PageProps) {
  const { tab } = await searchParams;
  return <MembersScreen initialTab={tab === "teams" ? "teams" : "members"} />;
}
