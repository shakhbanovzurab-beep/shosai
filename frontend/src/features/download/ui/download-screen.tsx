import { Info } from "lucide-react";
import { useTranslations } from "use-intl";

import { DESKTOP_PLATFORMS, type DesktopDownloads, type DesktopPlatform } from "../domain/contract";
import type { VisitorSystem } from "../domain/platform";
import { DesktopFeatures } from "./desktop-features";
import { InstallSteps } from "./install-steps";
import { PlatformCard } from "./platform-card";

/** Systems the desktop app doesn't run on get a note saying where it does. */
const NOTED = ["mobile", "linux"] as const;
const isNoted = (system: VisitorSystem): system is (typeof NOTED)[number] =>
  (NOTED as readonly VisitorSystem[]).includes(system);

type DownloadScreenProps = { downloads: DesktopDownloads; system: VisitorSystem };

/**
 * The desktop apps for macOS and Windows: the visitor's platform first and highlighted, then how to
 * install and what the app adds. Rendered on the server, so the right platform shows without a flash.
 */
export function DownloadScreen({ downloads, system }: DownloadScreenProps) {
  const t = useTranslations("download");
  const detected: DesktopPlatform | null = system === "macos" || system === "windows" ? system : null;
  const order = detected ? [detected, ...DESKTOP_PLATFORMS.filter((p) => p !== detected)] : [...DESKTOP_PLATFORMS];
  const note = isNoted(system) ? t(`notes.${system}`) : null;

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-10 pb-16">
      <header className="flex flex-col items-center gap-2 pt-2 text-center">
        <h1 className="font-semibold text-2xl tracking-tight sm:text-3xl">{t("title")}</h1>
        <p className="max-w-xl text-balance text-muted-foreground">{t("subtitle")}</p>
      </header>

      <div className="flex flex-col gap-4">
        {note ? (
          <p className="mx-auto flex max-w-4xl items-center gap-2 rounded-lg border bg-muted/40 px-4 py-3 text-sm">
            <Info className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            {note}
          </p>
        ) : null}
        <div className="mx-auto grid w-full max-w-4xl gap-4 md:grid-cols-2">
          {order.map((platform) => (
            <PlatformCard
              key={platform}
              platform={platform}
              release={downloads[platform]}
              recommended={platform === detected}
            />
          ))}
        </div>
      </div>

      <InstallSteps downloads={downloads} initial={detected ?? "macos"} />
      <DesktopFeatures mac={detected ? detected === "macos" : undefined} />
    </div>
  );
}
