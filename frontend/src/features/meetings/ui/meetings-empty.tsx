import Link from "next/link";

import { CalendarPlus, History, Upload, Video, VideoOff } from "lucide-react";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";

// Each state's title and description are `empty.<kind>` in the catalog; the action's text is `actions.<labelKey>`.
const STATES = {
  none: { icon: Video, action: { href: "/app/calendar", labelKey: "schedule", icon: CalendarPlus } },
  upcoming: { icon: CalendarPlus, action: { href: "/app/calendar", labelKey: "schedule", icon: CalendarPlus } },
  live: { icon: VideoOff, action: null },
  past: { icon: History, action: { href: "/app/notes", labelKey: "upload", icon: Upload } },
} as const;

export function MeetingsEmpty({ kind }: { kind: keyof typeof STATES }) {
  const t = useTranslations("meetings");
  const { icon: Icon, action } = STATES[kind];
  return (
    <Empty className="rounded-xl border border-dashed">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <Icon />
        </EmptyMedia>
        <EmptyTitle>{t(`empty.${kind}.title`)}</EmptyTitle>
        <EmptyDescription>{t(`empty.${kind}.description`)}</EmptyDescription>
      </EmptyHeader>
      {action ? (
        <EmptyContent>
          <Button asChild variant="outline">
            <Link href={action.href}>
              <action.icon data-icon="inline-start" />
              {t(`actions.${action.labelKey}`)}
            </Link>
          </Button>
        </EmptyContent>
      ) : null}
    </Empty>
  );
}
