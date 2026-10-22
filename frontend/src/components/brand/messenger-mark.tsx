import { cn } from "cn";
import { Hash } from "lucide-react";
import { siTelegram } from "simple-icons";

import { SimpleIcon } from "@/components/simple-icon";

/*
 * Знаки мессенджеров командных чатов: Telegram из simple-icons, у Slack знака там нет, поэтому — нейтральный
 * «#», как в списке коннекторов. Одноцветные, в цвете текста: работают в обеих темах. Для чтения с экрана
 * название мессенджера пишет тот, кто ставит знак.
 */

export type MessengerName = "telegram" | "slack";

export function MessengerMark({ messenger, className }: { messenger: MessengerName; className?: string }) {
  return messenger === "telegram" ? (
    <SimpleIcon icon={siTelegram} aria-hidden="true" className={cn("size-4", className)} />
  ) : (
    <Hash aria-hidden="true" className={cn("size-4", className)} />
  );
}

/** Знак в плитке, как у коннекторов: строка списка, выбор мессенджера. */
export function MessengerTile({ messenger }: { messenger: MessengerName }) {
  return (
    <span className="grid size-8 shrink-0 place-items-center rounded-lg border bg-background shadow-xs">
      <MessengerMark messenger={messenger} />
    </span>
  );
}
