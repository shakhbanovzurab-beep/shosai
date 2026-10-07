import { toast } from "sonner";

import { formatBytes } from "@/i18n/format-units";

import { MAX_RECORDING_BYTES } from "../domain/recordings";
import type { NotesWords } from "./words";

/**
 * Keeps audio and video files within the size limit, explaining every file that is turned away, in the
 * interface language (`locale` sizes the limit: "25 MB" / "25 МБ").
 */
export function filterRecordings(incoming: Iterable<File>, t: NotesWords, locale: string) {
  const accepted: File[] = [];
  for (const file of incoming) {
    if (!file.type.startsWith("audio/") && !file.type.startsWith("video/")) {
      toast.error(t("upload.notMedia", { name: file.name }));
    } else if (file.size > MAX_RECORDING_BYTES) {
      toast.error(t("upload.tooLarge", { name: file.name }), {
        description: t("upload.sizeLimit", { size: formatBytes(locale, MAX_RECORDING_BYTES) }),
      });
    } else {
      accepted.push(file);
    }
  }
  return accepted;
}
