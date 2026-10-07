import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { type FileManagerView, FolderView } from "@/features/file-manager";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("fileManager");
  return { title: t("meta.folderTitle") };
}

interface PageProps {
  params: Promise<{ folderId: string }>;
  searchParams: Promise<{ view?: string | string[] }>;
}

export default async function Page({ params, searchParams }: PageProps) {
  const [{ folderId }, { view }] = await Promise.all([params, searchParams]);
  const activeView: FileManagerView = view === "list" ? "list" : "grid";

  return <FolderView folderId={decodeURIComponent(folderId)} view={activeView} />;
}
