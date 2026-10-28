import { useEffect, useRef } from "react";

import { toast } from "sonner";
import { useTranslations } from "use-intl";

/**
 * Участникам — как в Zoom: когда владелец включает запись, приходит уведомление, а метка остаётся в шапке.
 * Владелец уведомления не получает: свою запись он только что включил сам. О записи, что шла до входа, говорит лобби.
 */
export function useRecordingNotice(recording: boolean, owner: boolean) {
  const t = useTranslations("meetingRoom");
  const before = useRef(recording);
  useEffect(() => {
    if (recording && !before.current && !owner) toast(t("recording.notice"));
    before.current = recording;
  }, [recording, owner, t]);
}
