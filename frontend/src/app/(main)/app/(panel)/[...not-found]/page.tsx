import { notFound } from "next/navigation";

import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("pages");
  return { title: t("notFound.metaTitle"), robots: { index: false } };
}

export default function CatchAllNotFound() {
  notFound();
}
