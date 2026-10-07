import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { ProductivityScreen } from "@/features/productivity";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("productivity");
  return {
    title: t("meta.title"),
    description: t("meta.description"),
    alternates: {
      canonical: "/app/productivity",
    },
  };
}

export default function Page() {
  return <ProductivityScreen />;
}
