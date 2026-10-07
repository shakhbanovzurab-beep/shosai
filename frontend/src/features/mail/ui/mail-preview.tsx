import Link from "next/link";

import { ExternalLink } from "lucide-react";
import { getTranslations } from "next-intl/server";

import { Button } from "@/components/ui/button";

/** The user panel's mail page: the standalone inbox embedded in an iframe, with a link to open it full screen. */
export async function MailPreview() {
  const t = await getTranslations("mail");

  return (
    <div className="flex h-full flex-col gap-2">
      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-col gap-0.5">
          <h1 className="font-medium text-sm leading-none">{t("preview.title")}</h1>
          <p className="text-muted-foreground text-sm">{t("preview.description")}</p>
        </div>
        <Button asChild variant="ghost" size="icon-sm">
          <Link
            href="/app/inbox"
            prefetch={false}
            target="_blank"
            rel="noreferrer"
            aria-label={t("preview.openInNewTab")}
          >
            <ExternalLink className="rtl:-scale-x-100" />
          </Link>
        </Button>
      </div>

      {/* First-party, same-origin preview of this app: a sandbox would cut it off from its own cookies,
          storage, and server requests without guarding against anything. */}
      {/* react-doctor-disable-next-line react-doctor/iframe-missing-sandbox */}
      <iframe src="/app/inbox" title={t("preview.title")} className="min-h-0 flex-1 rounded-lg border bg-background" />
    </div>
  );
}
