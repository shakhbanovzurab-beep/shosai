import Link from "next/link";

import { cn } from "cn";
import { CalendarClock, History, LayoutList, Radio } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";

import { type MeetingsView, viewHref } from "../domain/meeting";

// Each filter's name is `views.<view>` in the catalog.
const ITEMS: { view: MeetingsView; icon: typeof LayoutList }[] = [
  { view: "all", icon: LayoutList },
  { view: "upcoming", icon: CalendarClock },
  { view: "live", icon: Radio },
  { view: "past", icon: History },
];

/** The filters: a column beside the meetings on wide screens, a scrollable row above them on narrow ones. */
export function MeetingsNav({
  view,
  counts,
}: {
  view: MeetingsView | null;
  counts: Record<MeetingsView, number> | null;
}) {
  const t = useTranslations("meetings");
  const format = useFormatter();
  return (
    <nav aria-label={t("filters")} className="-mx-1 overflow-x-auto px-1 lg:mx-0 lg:overflow-visible lg:px-0">
      <ul className="flex gap-1 lg:flex-col">
        {ITEMS.map(({ view: item, icon: Icon }) => {
          const active = item === view;
          const count = counts?.[item];
          return (
            <li key={item} className="shrink-0">
              <Link
                href={viewHref(item)}
                scroll={false}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-ring",
                  active
                    ? "bg-muted font-medium text-foreground"
                    : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                )}
              >
                <Icon className="size-4" aria-hidden="true" />
                {t(`views.${item}`)}
                {item === "live" && count ? (
                  <span className="size-1.5 rounded-full bg-destructive" aria-hidden="true" />
                ) : null}
                {count === undefined ? null : (
                  <span className="ms-auto ps-2 text-muted-foreground text-xs tabular-nums">
                    {format.number(count)}
                  </span>
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
