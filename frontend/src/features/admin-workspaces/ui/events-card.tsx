"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import type { AdminEvent } from "../domain/contract";
import { formatFullDateTime, formatRelative } from "../domain/format";
import { eventText } from "../domain/labels";

const FIRST = 8;

/** What happened in the workspace, newest first: who did what, and when. The platform's own actions included. */
export function EventsCard({ events }: { events: AdminEvent[] }) {
  const [all, setAll] = useState(false);
  const shown = all ? events : events.slice(0, FIRST);
  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle>Журнал событий</CardTitle>
        <CardDescription>Приглашения, роли, настройки и действия администраторов платформы</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {events.length === 0 ? <p className="text-muted-foreground text-sm">Событий пока нет.</p> : null}
        <ol className="flex flex-col divide-y">
          {shown.map((event) => (
            <li key={event.id} className="flex flex-col gap-0.5 py-2.5 first:pt-0 last:pb-0">
              <span className="break-words text-sm">{eventText(event)}</span>
              <span className="text-muted-foreground text-xs">
                {event.actor ?? "Администратор платформы"} ·{" "}
                <time dateTime={event.at} title={formatFullDateTime(event.at)}>
                  {formatRelative(event.at)}
                </time>
              </span>
            </li>
          ))}
        </ol>
        {events.length > FIRST ? (
          <Button variant="ghost" size="sm" className="w-fit" onClick={() => setAll(!all)}>
            {all ? "Свернуть" : `Показать все (${events.length})`}
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}
