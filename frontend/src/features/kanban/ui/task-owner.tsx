import { cn } from "cn";
import { CircleUserRound } from "lucide-react";
import { useTranslations } from "use-intl";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { getInitials } from "@/lib/utils";

import type { Assignee } from "../domain/tasks-contract";
import { ownerTones, toneOf } from "./tones";

/** Аватар исполнителя или заглушка у задачи без исполнителя. */
export function OwnerAvatar({ owner }: { owner: Assignee | null }) {
  if (!owner) return <CircleUserRound className="size-5 text-muted-foreground" aria-hidden="true" />;
  return (
    <Avatar className={cn("size-5 after:rounded-sm", ownerTones[toneOf(owner.name)])}>
      <AvatarFallback className="rounded-sm text-[10px]">{getInitials(owner.name)}</AvatarFallback>
    </Avatar>
  );
}

/** Имя исполнителя, как его написали, или «Без исполнителя» на языке человека. */
export function OwnerName({ owner, className }: { owner: Assignee | null; className?: string }) {
  const t = useTranslations("kanban");
  if (!owner) return <span className={cn("truncate", className)}>{t("card.unassigned")}</span>;
  return (
    <span dir="auto" className={cn("truncate", className)}>
      {owner.name}
    </span>
  );
}
