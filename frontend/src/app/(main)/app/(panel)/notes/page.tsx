import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { NotesScreen, parseNotesView } from "@/features/notes";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("notes");
  return {
    title: t("meta.title"),
    description: t("meta.description"),
    alternates: {
      canonical: "/app/notes",
    },
  };
}

interface PageProps {
  searchParams: Promise<{ folder?: string | string[]; view?: string | string[] }>;
}

export default async function Page({ searchParams }: PageProps) {
  const { folder, view } = await searchParams;

  return <NotesScreen activeFolderId={typeof folder === "string" ? folder : undefined} view={parseNotesView(view)} />;
}
