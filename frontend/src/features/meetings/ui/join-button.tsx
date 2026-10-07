import type { ComponentProps } from "react";

import { ArrowUpRight } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";

import type { Meeting } from "../domain/meeting";

/**
 * Opens the call in a new tab: Google Meet, Zoom or Teams, or the LiveKit Meeting Room for a Whisperer
 * room. The call itself never runs on this page.
 */
export function JoinButton({
  meeting,
  ...props
}: { meeting: Meeting } & Omit<ComponentProps<typeof Button>, "asChild" | "children">) {
  const t = useTranslations("meetings");
  if (!meeting.joinUrl) return null;
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
