import { useLoaderData } from "react-router";
import { useTranslations } from "use-intl";

import { PageMeta } from "@/app/root/page-meta";
import type { DesktopDownloads } from "@/features/download/domain/contract";
import { detectSystem } from "@/features/download/domain/platform";
import { DownloadScreen } from "@/features/download/ui/download-screen";

type NavigatorWithHints = Navigator & { userAgentData?: { platform?: string } };

export function Component() {
  const t = useTranslations("download");
  const downloads = useLoaderData<DesktopDownloads>();
  const system = detectSystem(navigator.userAgent, (navigator as NavigatorWithHints).userAgentData?.platform ?? null);
  return (
    <>
      <PageMeta title={t("meta.title")} description={t("meta.description")} />
      <DownloadScreen downloads={downloads} system={system} />
    </>
  );
}
