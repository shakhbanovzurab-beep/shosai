import { Circle, Sparkles } from "lucide-react";
import { useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";

import type { CallMarks as Marks } from "../../domain/call-session";

/** Что идёт на сервере в звонке — заметки Leo и запись; видят все участники ещё до входа (MR-D3, MR-D4). */
export function CallMarks({ marks }: { marks: Marks }) {
  const t = useTranslations("meetingRoom");
  if (!marks.notes && !marks.recording) return null;
  return (
    <ul aria-label={t("marks.label")} className="flex flex-wrap items-center gap-2">
      {marks.notes ? (
        <li>
          <Badge variant="secondary">
            <Sparkles aria-hidden="true" />
            {t("marks.notes")}
          </Badge>
        </li>
      ) : null}
      {marks.recording ? (
        <li>
          <Badge variant="destructive">
            <Circle aria-hidden="true" className="fill-current" />
            {t("marks.recording")}
          </Badge>
        </li>
      ) : null}
    </ul>
  );
}
