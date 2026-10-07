import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { MeetingsScreen, parseMeetingsView } from "@/features/meetings";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("meetings");
  return {
    title: t("title"),
    alternates: {
      canonical: "/app/meetings",
    },
  };
}

interface PageProps {
  searchParams: Promise<{ view?: string | string[]; workspace?: string | string[] }>;
}

export default async function Page({ searchParams }: PageProps) {
  const { view, workspace } = await searchParams;
  return <MeetingsScreen view={parseMeetingsView(view)} sharedIn={typeof workspace === "string" ? workspace : null} />;
}
