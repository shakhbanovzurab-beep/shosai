import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { CreateWorkspace } from "@/features/workspace";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("workspace");
  return { title: t("meta.new"), robots: { index: false } };
}

export default function Page() {
  return <CreateWorkspace />;
}
