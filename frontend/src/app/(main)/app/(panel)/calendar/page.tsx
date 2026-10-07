import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { Calendar } from "@/features/calendar";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("calendar");
  return {
    title: t("meta.title"),
    description: t("meta.description"),
    alternates: {
      canonical: "/app/calendar",
    },
  };
}

export default function Page() {
  return <Calendar />;
}
