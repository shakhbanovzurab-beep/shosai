import type { ComponentProps } from "react";

import { ArrowRight, ArrowUpRight } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Link } from "@/lib/navigation";

import type { Meeting } from "../domain/meeting";

/** Своя комната Shosai открывается в кабинете; Google Meet, Zoom и Teams — в новой вкладке. */
export function JoinButton({
  meeting,
  ...props
}: { meeting: Meeting } & Omit<ComponentProps<typeof Button>, "asChild" | "children">) {
  const t = useTranslations("meetings");
  if (!meeting.joinUrl) return null;
  if (meeting.joinUrl.startsWith("/app/meet/"))
    return (
      <Button asChild {...props}>
        <Link href={meeting.joinUrl}>
          {t("join")}
          <ArrowRight data-icon="inline-end" className="rtl:-scale-x-100" />
        </Link>
      </Button>
    );
  return (
    <Button asChild {...props}>
      <a href={meeting.joinUrl} target="_blank" rel="noopener noreferrer">
        {t("join")}
        <ArrowUpRight data-icon="inline-end" className="rtl:-scale-x-100" />
        <span className="sr-only">{t("opensInNewTab")}</span>
      </a>
    </Button>
  );
}
