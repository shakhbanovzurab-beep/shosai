import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { AllFilesView, type FileManagerView } from "@/features/file-manager";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("fileManager");
  return {
    title: t("meta.title"),
    description: t("meta.description"),
    alternates: {
      canonical: "/app/file-manager",
    },
  };
}

interface PageProps {
  searchParams: Promise<{ view?: string | string[] }>;
}

export default async function Page({ searchParams }: PageProps) {
  const { view } = await searchParams;
  const activeView: FileManagerView = view === "list" ? "list" : "grid";

  return <AllFilesView view={activeView} />;
}
