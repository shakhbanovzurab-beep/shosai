import { useFormatter, useNow, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { meetingNotes } from "@/features/notes/data/meeting-notes";
import { Link } from "@/lib/navigation";

import { daysAgo } from "../domain/days";

/** The four latest notes, each opening in Notes. */
export function RecentNotesCard() {
  const t = useTranslations("productivity");
  const format = useFormatter();
  const now = useNow();
  const recent = meetingNotes.toSorted((a, b) => b.startedAt.localeCompare(a.startedAt)).slice(0, 4);

  // The notes' times are UTC, like the formatter, so "Today" and the dates agree with each other.
  const noteDay = (iso: string) => {
    const days = daysAgo(iso, now.getTime());
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
        {recent.length === 0 ? (
          <div className="flex flex-col gap-1 text-sm">
            <p className="font-medium">{t("notes.empty")}</p>
            <p className="text-muted-foreground">{t("notes.emptyHint")}</p>
          </div>
        ) : (
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
        )}
      </CardContent>
    </Card>
  );
}
