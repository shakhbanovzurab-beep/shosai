import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { UpgradeScreen } from "@/features/upgrade";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("upgrade");
  return {
    title: t("meta.title"),
    alternates: {
      canonical: "/app/upgrade",
    },
  };
}

export default function Page() {
  return <UpgradeScreen />;
}
