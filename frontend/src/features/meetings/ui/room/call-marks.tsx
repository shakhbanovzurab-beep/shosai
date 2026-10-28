import { Circle, Sparkles } from "lucide-react";
import { useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";

import type { CallMarks as Marks } from "../../domain/call-session";

/** Что идёт на сервере в звонке — заметки Leo и запись; лобби говорит о них каждому ещё до входа (MR-D3, MR-D4). */
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
            <Circle aria-hidden="true" className="fill-current motion-safe:animate-pulse" />
            {t("marks.recording")}
          </Badge>
        </li>
      ) : null}
    </ul>
  );
}

/** Метка записи в шапке идущего звонка, как в Zoom: красная точка видна всем, пока запись идёт. */
export function RecordingMark({ recording }: { recording: boolean }) {
  const t = useTranslations("meetingRoom");
  if (!recording) return null;
  return (
    <Badge variant="destructive">
      <Circle aria-hidden="true" className="fill-current motion-safe:animate-pulse" />
      {t("marks.recording")}
    </Badge>
  );
}
