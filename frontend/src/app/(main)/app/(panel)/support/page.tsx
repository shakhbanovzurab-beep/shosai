import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { SupportScreen } from "@/features/support";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("pagesSupport");
  return {
    title: t("meta.title"),
    description: t("meta.description"),
    alternates: {
      canonical: "/app/support",
    },
  };
}

export default function Page() {
  return <SupportScreen />;
}
