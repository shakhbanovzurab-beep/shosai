import { getTranslations } from "next-intl/server";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { DESKTOP_PLATFORMS, type DesktopDownloads, type DesktopPlatform } from "../domain/contract";
import { fileType } from "../domain/format";
import { orderBuilds, PLATFORM_NAME } from "../domain/platform";

/** The installer's extension for the steps, from the published build, or the usual one. */
function installerType(platform: DesktopPlatform, downloads: DesktopDownloads) {
  const release = downloads[platform];
  const fallback = platform === "macos" ? ".dmg" : ".exe";
  if (!release || release === "error" || release.files.length === 0) return fallback;
  return fileType(orderBuilds(platform, release.files).primary.file_name) || fallback;
}

type Words = Awaited<ReturnType<typeof getTranslations<"download">>>;

function steps(t: Words, platform: DesktopPlatform, type: string) {
  if (platform === "macos")
    return [t("install.macos.open", { type }), t("install.macos.drag"), t("install.macos.allow")];
  return [t("install.windows.run", { type }), t("install.windows.setup"), t("install.windows.allow")];
}

/** Three steps from download to the first meeting, for the visitor's platform first. */
export async function InstallSteps({ downloads, initial }: { downloads: DesktopDownloads; initial: DesktopPlatform }) {
  const t = await getTranslations("download");
  return (
    <section aria-labelledby="install-steps" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id="install-steps" className="font-semibold text-lg">
          {t("install.title")}
        </h2>
      </div>
      <Tabs defaultValue={initial} className="gap-4">
        <TabsList>
          {DESKTOP_PLATFORMS.map((platform) => (
            <TabsTrigger key={platform} value={platform}>
              {PLATFORM_NAME[platform]}
            </TabsTrigger>
          ))}
        </TabsList>
        {DESKTOP_PLATFORMS.map((platform) => (
          <TabsContent key={platform} value={platform}>
            <ol className="grid gap-3 md:grid-cols-3">
              {steps(t, platform, installerType(platform, downloads)).map((text, index) => (
                <li key={text} className="flex gap-3 rounded-xl border bg-card p-4 text-sm">
                  <span
                    aria-hidden="true"
                    className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary font-medium text-primary-foreground text-xs"
                  >
                    {index + 1}
                  </span>
                  <span className="pt-0.5">{text}</span>
                </li>
              ))}
            </ol>
          </TabsContent>
        ))}
      </Tabs>
    </section>
  );
}
