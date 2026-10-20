import { useFormatter, useTranslations } from "use-intl";

import { CALENDAR_DAY } from "@/i18n/calendar-days";

import type { WriteUpFinding } from "../domain/write-up";

/**
 * Задачи из записи Leo, только для чтения (MT-D4): что сделать, на ком и к какому сроку, если встреча это
 * сказала. Отмечать их будет один список задач, когда он появится.
 */
export function ActionItems({ items }: { readonly items: readonly WriteUpFinding[] }) {
  const t = useTranslations("notesNote");
  const format = useFormatter();
  return (
    <ul className="flex flex-col gap-2.5">
      {items.map((item) => (
        <li key={item.id} className="flex flex-col gap-0.5 rounded-lg border bg-card px-3 py-2 text-sm">
          <span dir="auto">{item.text}</span>
          {item.ownerName || item.dueOn ? (
            <span className="flex flex-wrap gap-x-3 text-muted-foreground text-xs">
              {item.ownerName ? <span dir="auto">{item.ownerName}</span> : null}
              {item.dueOn ? (
                <time dateTime={item.dueOn}>
                  {t("actionItems.due", { date: format.dateTime(new Date(item.dueOn), "short", CALENDAR_DAY) })}
                </time>
              ) : null}
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
