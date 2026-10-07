import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { WorkspaceFilePicker } from "@/features/file-manager";
import { TeamKnowledgeScreen } from "@/features/workspace";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("workspace");
  return { title: t("meta.knowledge"), robots: { index: false } };
}

// The workspace owns the "share from my files" dialog; File Manager supplies the list of files in it.
export default function Page() {
  return <TeamKnowledgeScreen picker={<WorkspaceFilePicker />} />;
}
