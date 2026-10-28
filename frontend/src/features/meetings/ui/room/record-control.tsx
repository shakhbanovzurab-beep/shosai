import { useState } from "react";

import { Circle, Square } from "lucide-react";
import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { Spinner } from "@/components/ui/spinner";
import { Toggle } from "@/components/ui/toggle";
import { ApiError } from "@/lib/api/errors";

// Отказы сервера записи (MR-D4), которые человек понимает и может исправить сам; прочее — «не вышло».
const REFUSALS = {
  recording_not_in_plan: "recording.notInPlan",
  storage_limit: "recording.storageFull",
  recordings_busy: "recording.busy",
  no_live_call: "recording.noCall",
  recording_not_active: "recording.notActive",
} as const;
const isRefusal = (code: string | null): code is keyof typeof REFUSALS =>
  code !== null && Object.hasOwn(REFUSALS, code);
// Метка записи приходит от сервера записи; не пришла за 30 с — кнопка снова доступна.
const MARK_WAIT_MS = 30_000;

type RecordControlProps = { recording: boolean; onRecording: (on: boolean) => Promise<void> };

/** Запись встречи владельцем, как в Zoom: начать и остановить; файл ложится в его «Файлы», метку видят все. */
export function RecordControl({ recording, onRecording }: RecordControlProps) {
  const t = useTranslations("meetingRoom");
  // Какое состояние записи запрошено и ещё не пришло меткой; null — ничего не ждём.
  const [requested, setRequested] = useState<boolean | null>(null);
  const waiting = requested !== null && requested !== recording;

  const request = async (on: boolean) => {
    setRequested(on);
    try {
      await onRecording(on);
    } catch (error) {
      setRequested(null);
      const code = error instanceof ApiError ? error.code : null;
      const failed = on ? "recording.startFailed" : "recording.stopFailed";
      toast.error(t(isRefusal(code) ? REFUSALS[code] : failed));
      return;
    }
    toast(t(on ? "recording.started" : "recording.stopped"));
    window.setTimeout(() => setRequested(null), MARK_WAIT_MS);
  };

  let icon = <Circle aria-hidden="true" className="fill-current text-destructive" />;
  if (recording) icon = <Square aria-hidden="true" className="fill-current text-destructive" />;
  if (waiting) icon = <Spinner />;
  return (
    <Toggle
      variant="outline"
      // Пока метка не пришла, кнопка уже показывает запрошенное: запрошенное и есть то, что будет.
      pressed={requested ?? recording}
      disabled={waiting}
      onPressedChange={(on) => void request(on)}
      aria-label={t(recording ? "controls.stopRecording" : "controls.record")}
    >
      {icon}
    </Toggle>
  );
}
