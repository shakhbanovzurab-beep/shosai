"use client";

import { Copy, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { copyText } from "@/lib/copy-text";

import type { DesktopBuild, DesktopPlatform } from "../domain/contract";

const VERIFY_COMMAND: Record<DesktopPlatform, (file: string) => string> = {
  macos: (file) => `shasum -a 256 ~/Downloads/${file}`,
  windows: (file) => `certutil -hashfile %USERPROFILE%\\Downloads\\${file} SHA256`,
};

/** The build's SHA-256, to check the download wasn't altered, with the command that computes it. */
export function ChecksumButton({ build, platform }: { build: DesktopBuild; platform: DesktopPlatform }) {
  const t = useTranslations("download");
  const copy = async () => {
    try {
      await copyText(build.sha256);
      toast.success(t("checksum.copied"));
    } catch {
      toast.error(t("checksum.copyFailed"));
    }
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="xs" className="text-muted-foreground">
          <ShieldCheck data-icon="inline-start" />
          {t("checksum.button")}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="flex w-80 flex-col gap-3 text-sm">
        <div className="flex flex-col gap-1">
          <span className="font-medium">
            {/* i18n-ignore: the algorithm's name and the file's, the same in every language */}
            SHA-256 · <bdi>{build.file_name}</bdi>
          </span>
          <code className="break-all rounded-md bg-muted px-2 py-1.5 font-mono text-xs">{build.sha256}</code>
        </div>
        <p className="text-muted-foreground text-xs">
          {t.rich("checksum.verify", {
            command: VERIFY_COMMAND[platform](build.file_name),
            code: (chunks) => (
              <code className="break-all font-mono" dir="ltr">
                {chunks}
              </code>
            ),
          })}
        </p>
        <Button variant="outline" size="sm" onClick={() => void copy()}>
          <Copy data-icon="inline-start" />
          {t("checksum.copy")}
        </Button>
      </PopoverContent>
    </Popover>
  );
}
