import { ChartColumn, FileText, Globe, ListChecks, Mail, NotebookPen, Video } from "lucide-react";

import type { SourceKind } from "../../domain/sources";

/** Значок источника по его виду: один и тот же в фишке под ответом и в раскрытом отрывке. */
export const SOURCE_ICONS: Record<SourceKind, typeof FileText> = {
  meeting: Video,
  file: FileText,
  task: ListChecks,
  note: NotebookPen,
  mail: Mail,
  web: Globe,
  report: ChartColumn,
};
