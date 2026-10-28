import { CalendarClock, DoorOpen, Hourglass, type LucideIcon, RadioTower, Users } from "lucide-react";
import { useTranslations } from "use-intl";

import { RoomState } from "../room/room-problem";

export type OutsideKind = "not_live" | "wait" | "full" | "ended" | "left";

const ICONS: Record<OutsideKind, LucideIcon> = {
  not_live: CalendarClock,
  wait: Hourglass,
  full: Users,
  ended: RadioTower,
  left: DoorOpen,
};

/** Трансляция не пускает в эфир: ещё не началась, ждёт впуска, мест нет, закончилась или человек вышел сам. */
export function BroadcastOutside({ kind, onRetry }: { kind: OutsideKind; onRetry: (() => void) | null }) {
  const t = useTranslations("meetingBroadcast");
  const label = kind === "left" ? t("outside.rejoin") : t("outside.tryAgain");
  const retry = onRetry && (kind === "not_live" || kind === "full" || kind === "left");
  return (
    <RoomState
      icon={ICONS[kind]}
      title={t(`outside.${kind}.title`)}
      description={t(`outside.${kind}.description`)}
      action={retry ? { label, run: onRetry } : null}
    />
  );
}
