import { useFormatter, useNow, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useRecentNotes } from "@/features/notes/model/recent-notes";
import { useTimeZone } from "@/i18n/time-zone";
import { Link } from "@/lib/navigation";

import { daysAgo } from "../domain/days";

/** Четыре последние встречи с сервера, каждая открывается в «Заметках». */
export function RecentNotesCard() {
  const t = useTranslations("productivity");
  const format = useFormatter();
  const now = useNow();
  const zone = useTimeZone();
  const state = useRecentNotes();
  const recent = state.status === "ready" ? state.data : [];

  // Дни и даты — в одном поясе кабинета, поэтому «Сегодня» и даты не расходятся.
  const noteDay = (iso: string) => {
    const days = daysAgo(iso, now.getTime(), zone);
    if (days === 0) return t("notes.today");
    if (days === 1) return t("notes.yesterday");
    return format.dateTime(new Date(iso), "short");
  };

  return (
    <Card className="shadow-xs">
      <CardHeader>
        <CardTitle>{t("notes.heading")}</CardTitle>
        <CardAction>
          <Button asChild variant="ghost" size="sm" className="text-muted-foreground">
            <Link href="/app/notes">{t("notes.viewAll")}</Link>
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {state.status === "loading" ? (
          <div className="flex flex-col gap-3" aria-busy="true">
            {[0, 1, 2, 3].map((row) => (
              <Skeleton key={row} className="h-4 w-3/4" />
            ))}
          </div>
        ) : null}
        {state.status === "error" ? <p className="text-muted-foreground text-sm">{t("notes.loadFailed")}</p> : null}
        {state.status === "ready" && recent.length === 0 ? (
          <div className="flex flex-col gap-1 text-sm">
            <p className="font-medium">{t("notes.empty")}</p>
            <p className="text-muted-foreground">{t("notes.emptyHint")}</p>
          </div>
        ) : null}
        {recent.length > 0 ? (
          <ul className="-mx-2 flex flex-col">
            {recent.map((note) => (
              <li key={note.id}>
                <Link
                  href={`/app/notes/${note.id}`}
                  className="flex flex-col gap-0.5 rounded-md px-2 py-1.5 outline-none hover:bg-muted focus-visible:ring-3 focus-visible:ring-ring/50"
                >
                  <span className="truncate font-medium text-sm">
                    <span dir="auto">{note.title}</span>
                  </span>
                  <time dateTime={note.startedAt} className="text-muted-foreground text-xs">
                    {noteDay(note.startedAt)}
                  </time>
                </Link>
              </li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}
