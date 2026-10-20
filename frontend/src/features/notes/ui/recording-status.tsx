import { useFormatter, useTranslations } from "use-intl";

import type { RecordingUpload } from "../model/recording-uploads";

/**
 * Что с загружаемой записью: сколько ушло в бакет или почему загрузка не вышла. Проценты видны, но не
 * озвучиваются: живой регион вокруг сообщает читалке экрана о начале загрузки и об отказе, а не о каждом шаге.
 */
export function RecordingStatus({ recording }: { readonly recording: RecordingUpload }) {
  const t = useTranslations("notes");
  const format = useFormatter();
  if (recording.failed !== null) return <span className="text-destructive">{recording.failed}</span>;
  const share = recording.size > 0 ? recording.sent / recording.size : 0;
  return (
    <>
      <span aria-hidden="true">
        {t("recordings.uploadingShare", { share: format.number(Math.min(share, 1), "percent") })}
      </span>
      <span className="sr-only">{t("recordings.uploading")}</span>
    </>
  );
}
