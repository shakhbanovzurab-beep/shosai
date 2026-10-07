import { cn } from "cn";
import { CircleAlert, Clock, Download } from "lucide-react";
import { getFormatter, getLocale, getTranslations } from "next-intl/server";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatBytes } from "@/i18n/format-units";

import type { DesktopPlatform, DesktopRelease } from "../domain/contract";
import { fileType } from "../domain/format";
import { archName, minimumSystem, orderBuilds, PLATFORM_NAME, UNIVERSAL_ARCH } from "../domain/platform";
import { ChecksumButton } from "./checksum-button";
import { OsIcon } from "./os-icon";
import { RetryButton } from "./retry-button";

type PlatformCardProps = {
  platform: DesktopPlatform;
  release: DesktopRelease | null | "error";
  /** The visitor is on this platform: the card is highlighted and listed first. */
  recommended: boolean;
};

async function Unavailable({ platform, error }: { platform: DesktopPlatform; error: boolean }) {
  const t = await getTranslations("download");
  const Icon = error ? CircleAlert : Clock;
  return (
    <div className="flex flex-col gap-3">
      <p className="flex items-center gap-2 text-muted-foreground text-sm">
        <Icon className="size-4 shrink-0" aria-hidden="true" />
        {error
          ? t("card.loadFailed", { platform: PLATFORM_NAME[platform] })
          : t("card.notYet", { platform: PLATFORM_NAME[platform] })}
      </p>
      {error ? <RetryButton /> : null}
    </div>
  );
}

/** One platform: what it needs, the main download, other builds, and the checksum. */
export async function PlatformCard({ platform, release, recommended }: PlatformCardProps) {
  const [t, format, locale] = await Promise.all([getTranslations("download"), getFormatter(), getLocale()]);
  const name = PLATFORM_NAME[platform];
  const titleId = `download-${platform}`;
  const ready = release !== null && release !== "error" && release.files.length > 0 ? release : null;
  const builds = ready ? orderBuilds(platform, ready.files) : null;
  const arch = (code: string) => (code === UNIVERSAL_ARCH ? t("card.universal") : archName(code));

  return (
    <article
      aria-labelledby={titleId}
      className={cn(
        "flex flex-col gap-5 rounded-xl border bg-card p-6",
        recommended && "shadow-sm ring-2 ring-primary",
      )}
    >
      <div className="flex items-start gap-4">
        <span className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-muted">
          <OsIcon platform={platform} className="size-6" />
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 id={titleId} className="font-semibold text-lg">
              {name}
            </h2>
            {recommended ? <Badge variant="secondary">{t("card.yourComputer")}</Badge> : null}
          </div>
          {ready && builds ? (
            <p className="text-muted-foreground text-sm">
              {t("card.requirement", { system: minimumSystem(platform, ready.min_os_version) })} ·{" "}
              {arch(builds.primary.arch)}
            </p>
          ) : null}
        </div>
      </div>

      {ready && builds ? (
        <>
          <div className="flex flex-1 flex-col gap-2">
            <Button asChild size="lg" variant={recommended ? "default" : "outline"} className="w-full">
              <a href={builds.primary.url} download={builds.primary.file_name}>
                <Download data-icon="inline-start" />
                {t("card.downloadFor", { name })}
              </a>
            </Button>
            {builds.others.map((build) => (
              <a
                key={build.arch}
                href={build.url}
                download={build.file_name}
                className="text-center text-muted-foreground text-sm underline-offset-4 hover:text-foreground hover:underline"
              >
                {t("card.downloadBuild", { arch: arch(build.arch), size: formatBytes(locale, build.size_bytes) })}
              </a>
            ))}
          </div>
          <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t pt-4 text-muted-foreground text-xs">
            <span className="tabular-nums">
              {t("card.meta", {
                version: ready.version,
                size: formatBytes(locale, builds.primary.size_bytes),
                type: fileType(builds.primary.file_name),
                // A release day: published_at is UTC and next-intl formats in UTC.
                date: format.dateTime(new Date(ready.published_at), "medium"),
              })}
            </span>
            <ChecksumButton build={builds.primary} platform={platform} />
          </div>
        </>
      ) : (
        <Unavailable platform={platform} error={release === "error"} />
      )}
    </article>
  );
}
