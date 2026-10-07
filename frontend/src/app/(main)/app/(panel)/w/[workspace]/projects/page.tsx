import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { ProjectsScreen } from "@/features/workspace";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("workspace");
  return { title: t("meta.projects"), robots: { index: false } };
}

export default function Page() {
  return <ProjectsScreen />;
}
