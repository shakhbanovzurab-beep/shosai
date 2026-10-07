import { headers } from "next/headers";

import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { DownloadScreen, detectSystem } from "@/features/download";
import { getDesktopDownloads } from "@/features/download/server";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("download");
  return {
    title: t("meta.title"),
    description: t("meta.description"),
    alternates: {
      canonical: "/app/download",
    },
  };
}

export default async function Page() {
  const [downloads, requestHeaders] = await Promise.all([getDesktopDownloads(), headers()]);
  const system = detectSystem(requestHeaders.get("user-agent"), requestHeaders.get("sec-ch-ua-platform"));
  return <DownloadScreen downloads={downloads} system={system} />;
}
